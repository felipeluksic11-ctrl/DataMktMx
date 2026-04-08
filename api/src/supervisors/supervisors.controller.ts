import {
  Controller,
  Get,
  Patch,
  Post,
  Param,
  Query,
  Body,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { RedisService } from '../redis.service';

@Controller('supervisors')
export class SupervisorsController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
  ) {}

  // ── Supervisor Runs ──────────────────────────────────────────

  @Get('runs')
  async findRuns(
    @Query('page') page = '1',
    @Query('limit') limit = '20',
    @Query('portalId') portalId?: string,
    @Query('status') status?: string,
  ) {
    const skip = (Number(page) - 1) * Number(limit);
    const where: Record<string, unknown> = {};
    if (portalId) where.portalId = portalId;
    if (status) where.status = status;

    const [runs, total] = await Promise.all([
      this.prisma.supervisorRun.findMany({
        where,
        include: {
          portal: { select: { id: true, name: true, slug: true } },
          _count: { select: { repairLogs: true } },
        },
        orderBy: { createdAt: 'desc' },
        skip,
        take: Number(limit),
      }),
      this.prisma.supervisorRun.count({ where }),
    ]);

    return { data: runs, total, page: Number(page), limit: Number(limit) };
  }

  @Get('runs/:id')
  async findRun(@Param('id') id: string) {
    const run = await this.prisma.supervisorRun.findUnique({
      where: { id },
      include: {
        portal: { select: { id: true, name: true, slug: true } },
        repairLogs: { orderBy: { createdAt: 'desc' } },
      },
    });
    if (!run) throw new NotFoundException(`SupervisorRun ${id} not found`);
    return run;
  }

  // ── Repair Logs ──────────────────────────────────────────────

  @Get('repairs')
  async findRepairs(
    @Query('page') page = '1',
    @Query('limit') limit = '20',
    @Query('portalId') portalId?: string,
    @Query('status') status?: string,
    @Query('field') field?: string,
  ) {
    const skip = (Number(page) - 1) * Number(limit);
    const where: Record<string, unknown> = {};
    if (portalId) where.portalId = portalId;
    if (status) where.status = status;
    if (field) where.field = field;

    const [repairs, total] = await Promise.all([
      this.prisma.repairLog.findMany({
        where,
        include: {
          portal: { select: { id: true, name: true, slug: true } },
          supervisorRun: { select: { id: true, trigger: true, createdAt: true } },
        },
        orderBy: { createdAt: 'desc' },
        skip,
        take: Number(limit),
      }),
      this.prisma.repairLog.count({ where }),
    ]);

    return { data: repairs, total, page: Number(page), limit: Number(limit) };
  }

  @Patch('repairs/:id/apply')
  async applyRepair(@Param('id') id: string) {
    const repair = await this.prisma.repairLog.findUnique({ where: { id } });
    if (!repair) throw new NotFoundException(`RepairLog ${id} not found`);
    if (repair.status !== 'queued') {
      return { message: `Repair is ${repair.status}, cannot apply` };
    }

    // Apply the selector override to the portal
    const portal = await this.prisma.portal.findUnique({
      where: { id: repair.portalId },
    });
    if (!portal) throw new NotFoundException('Portal not found');

    const currentOverrides = (portal.selectorOverrides ?? {}) as Record<string, string>;
    const newOverrides = { ...currentOverrides };
    if (repair.newSelector) {
      newOverrides[repair.field] = repair.newSelector;
    }

    await this.prisma.$transaction([
      this.prisma.portal.update({
        where: { id: repair.portalId },
        data: { selectorOverrides: newOverrides as object },
      }),
      this.prisma.repairLog.update({
        where: { id },
        data: {
          status: 'manually_applied',
          appliedAt: new Date(),
          appliedBy: 'admin',
        },
      }),
    ]);

    return { message: 'Repair applied', field: repair.field };
  }

  @Patch('repairs/:id/reject')
  async rejectRepair(@Param('id') id: string) {
    const repair = await this.prisma.repairLog.findUnique({ where: { id } });
    if (!repair) throw new NotFoundException(`RepairLog ${id} not found`);

    return this.prisma.repairLog.update({
      where: { id },
      data: { status: 'rejected' },
    });
  }

  // ── Supervisor Configs ───────────────────────────────────────

  @Get('configs')
  async findConfigs() {
    return this.prisma.supervisorConfig.findMany({
      include: {
        portal: { select: { id: true, name: true, slug: true } },
      },
    });
  }

  @Patch('configs/:id')
  async updateConfig(
    @Param('id') id: string,
    @Body() body: Partial<{
      isEnabled: boolean;
      runAfterScrape: boolean;
      autoApplyThreshold: number;
      queueReviewThreshold: number;
      maxDailyCostUsd: number;
      cronExpression: string | null;
    }>,
  ) {
    const existing = await this.prisma.supervisorConfig.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`SupervisorConfig ${id} not found`);

    return this.prisma.supervisorConfig.update({
      where: { id },
      data: body,
    });
  }

  // ── Manual Trigger ───────────────────────────────────────────

  @Post('diagnose/:portalId')
  async diagnose(@Param('portalId') portalId: string) {
    const portal = await this.prisma.portal.findUnique({ where: { id: portalId } });
    if (!portal) throw new NotFoundException(`Portal ${portalId} not found`);

    await this.redis.publish(
      'supervisor:manual_trigger',
      JSON.stringify({ portal_id: portalId, portal_slug: portal.slug }),
    );

    return { message: `Diagnostic queued for ${portal.name}` };
  }
}
