import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Body,
  Query,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { RedisService } from '../redis.service';

@Controller('schedules')
export class SchedulesController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
  ) {}

  // ── Schedule Configs ─────────────────────────────────────────

  @Get()
  async findAll() {
    const schedules = await this.prisma.scheduleConfig.findMany({
      include: {
        portal: { select: { id: true, name: true, slug: true, isActive: true } },
        group: { select: { id: true, name: true } },
        _count: { select: { scheduleRuns: true } },
      },
      orderBy: [{ priority: 'desc' }, { name: 'asc' }],
    });

    return schedules.map((s) => ({
      ...s,
      runCount: s._count.scheduleRuns,
      _count: undefined,
    }));
  }

  @Get('health')
  async health() {
    const [running, queued, totalSchedules] = await Promise.all([
      this.prisma.scheduleRun.count({ where: { status: 'running' } }),
      this.prisma.scheduleRun.count({ where: { status: 'queued' } }),
      this.prisma.scheduleConfig.count({ where: { isEnabled: true } }),
    ]);

    const nextRun = await this.prisma.scheduleConfig.findFirst({
      where: { isEnabled: true, nextRunAt: { not: null } },
      orderBy: { nextRunAt: 'asc' },
      select: { name: true, nextRunAt: true, portal: { select: { slug: true } } },
    });

    return {
      running,
      queued,
      totalSchedules,
      nextRun: nextRun
        ? { name: nextRun.name, nextRunAt: nextRun.nextRunAt, portal: nextRun.portal.slug }
        : null,
    };
  }

  @Get('queue')
  async queue() {
    const runs = await this.prisma.scheduleRun.findMany({
      where: { status: { in: ['queued', 'running'] } },
      include: {
        schedule: {
          select: {
            name: true,
            mode: true,
            budgetMb: true,
            portal: { select: { name: true, slug: true } },
          },
        },
      },
      orderBy: { queuedAt: 'asc' },
    });

    return runs;
  }

  @Get('runs')
  async findRuns(
    @Query('page') page = '1',
    @Query('limit') limit = '20',
    @Query('scheduleId') scheduleId?: string,
    @Query('status') status?: string,
  ) {
    const skip = (Number(page) - 1) * Number(limit);
    const where: Record<string, unknown> = {};
    if (scheduleId) where.scheduleId = scheduleId;
    if (status) where.status = status;

    const [runs, total] = await Promise.all([
      this.prisma.scheduleRun.findMany({
        where,
        include: {
          schedule: {
            select: {
              name: true,
              mode: true,
              portal: { select: { name: true, slug: true } },
            },
          },
          scrapeJob: {
            select: { id: true, status: true, totalScraped: true, totalNew: true, totalErrors: true },
          },
        },
        orderBy: { queuedAt: 'desc' },
        skip,
        take: Number(limit),
      }),
      this.prisma.scheduleRun.count({ where }),
    ]);

    return { data: runs, total, page: Number(page), limit: Number(limit) };
  }

  @Post()
  async create(
    @Body()
    body: {
      name: string;
      portalId: string;
      mode: string;
      cronExpression: string;
      budgetMb: number;
      groupId?: string;
      states?: string[];
      visitDetail?: boolean;
      priority?: number;
      rateLimitS?: number;
      maxRetries?: number;
      retryBackoffS?: number;
    },
  ) {
    return this.prisma.scheduleConfig.create({
      data: {
        name: body.name,
        portalId: body.portalId,
        mode: body.mode,
        cronExpression: body.cronExpression,
        budgetMb: body.budgetMb,
        groupId: body.groupId,
        states: body.states,
        visitDetail: body.visitDetail ?? false,
        priority: body.priority ?? 50,
        rateLimitS: body.rateLimitS ?? 0,
        maxRetries: body.maxRetries ?? 3,
        retryBackoffS: body.retryBackoffS ?? 300,
      },
      include: {
        portal: { select: { id: true, name: true, slug: true } },
      },
    });
  }

  @Patch(':id')
  async update(
    @Param('id') id: string,
    @Body() body: Partial<{
      name: string;
      cronExpression: string;
      budgetMb: number;
      states: string[];
      visitDetail: boolean;
      priority: number;
      rateLimitS: number;
      maxRetries: number;
      retryBackoffS: number;
      groupId: string | null;
      mode: string;
    }>,
  ) {
    const existing = await this.prisma.scheduleConfig.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`Schedule ${id} not found`);

    return this.prisma.scheduleConfig.update({
      where: { id },
      data: body,
      include: {
        portal: { select: { id: true, name: true, slug: true } },
      },
    });
  }

  @Patch(':id/toggle')
  async toggle(@Param('id') id: string) {
    const existing = await this.prisma.scheduleConfig.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`Schedule ${id} not found`);

    return this.prisma.scheduleConfig.update({
      where: { id },
      data: { isEnabled: !existing.isEnabled },
    });
  }

  @Post(':id/run-now')
  async runNow(@Param('id') id: string) {
    const existing = await this.prisma.scheduleConfig.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`Schedule ${id} not found`);

    // Create a queued run record
    const run = await this.prisma.scheduleRun.create({
      data: {
        scheduleId: id,
        trigger: 'manual',
        status: 'queued',
      },
    });

    // Publish to Redis for the scheduler daemon to pick up
    await this.redis.publish(
      'scheduler:trigger',
      JSON.stringify({ schedule_id: id, run_id: run.id }),
    );

    return { message: 'Run queued', runId: run.id };
  }

  @Delete(':id')
  async remove(@Param('id') id: string) {
    const existing = await this.prisma.scheduleConfig.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`Schedule ${id} not found`);

    await this.prisma.scheduleConfig.delete({ where: { id } });
    return { message: 'Schedule deleted' };
  }

  // ── Schedule Groups ──────────────────────────────────────────

  @Get('groups')
  async findGroups() {
    return this.prisma.scheduleGroup.findMany({
      include: {
        scheduleConfigs: {
          select: { id: true, name: true, mode: true, isEnabled: true, portal: { select: { name: true, slug: true } } },
          orderBy: { priority: 'desc' },
        },
      },
      orderBy: { name: 'asc' },
    });
  }

  @Post('groups')
  async createGroup(
    @Body() body: { name: string; description?: string; executionMode?: string; staggerSeconds?: number },
  ) {
    return this.prisma.scheduleGroup.create({
      data: {
        name: body.name,
        description: body.description,
        executionMode: body.executionMode ?? 'sequential',
        staggerSeconds: body.staggerSeconds ?? 1800,
      },
    });
  }

  @Patch('groups/:id')
  async updateGroup(
    @Param('id') id: string,
    @Body() body: Partial<{ name: string; description: string; isEnabled: boolean; executionMode: string; staggerSeconds: number }>,
  ) {
    const existing = await this.prisma.scheduleGroup.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`Group ${id} not found`);

    return this.prisma.scheduleGroup.update({ where: { id }, data: body });
  }

  @Post('groups/:id/run-now')
  async runGroupNow(@Param('id') id: string) {
    const group = await this.prisma.scheduleGroup.findUnique({
      where: { id },
      include: {
        scheduleConfigs: {
          where: { isEnabled: true },
          orderBy: { priority: 'desc' },
        },
      },
    });
    if (!group) throw new NotFoundException(`Group ${id} not found`);

    const runs = [];
    for (const sched of group.scheduleConfigs) {
      const run = await this.prisma.scheduleRun.create({
        data: { scheduleId: sched.id, trigger: 'manual', status: 'queued' },
      });
      await this.redis.publish(
        'scheduler:trigger',
        JSON.stringify({ schedule_id: sched.id, run_id: run.id }),
      );
      runs.push({ scheduleId: sched.id, runId: run.id });
    }

    return { message: `${runs.length} runs queued`, runs };
  }
}
