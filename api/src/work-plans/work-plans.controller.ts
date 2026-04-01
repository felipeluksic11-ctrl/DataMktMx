import {
  Controller,
  Get,
  Patch,
  Param,
  NotFoundException,
  BadRequestException,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Controller('work-plans')
export class WorkPlansController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async findAll() {
    const plans = await this.prisma.workPlan.findMany({
      include: {
        portal: { select: { name: true, slug: true } },
      },
      orderBy: { createdAt: 'desc' },
    });

    return plans;
  }

  @Get(':id')
  async findOne(@Param('id') id: string) {
    const plan = await this.prisma.workPlan.findUnique({
      where: { id },
      include: {
        portal: { select: { name: true, slug: true } },
      },
    });

    if (!plan) {
      throw new NotFoundException(`WorkPlan ${id} not found`);
    }

    return plan;
  }

  @Patch(':id/approve')
  async approve(@Param('id') id: string) {
    const plan = await this.prisma.workPlan.findUnique({ where: { id } });

    if (!plan) {
      throw new NotFoundException(`WorkPlan ${id} not found`);
    }
    if (plan.status !== 'draft') {
      throw new BadRequestException(
        `Cannot approve a plan with status "${plan.status}". Only draft plans can be approved.`,
      );
    }

    return this.prisma.workPlan.update({
      where: { id },
      data: {
        status: 'approved',
        approvedAt: new Date(),
      },
    });
  }

  @Patch(':id/cancel')
  async cancel(@Param('id') id: string) {
    const plan = await this.prisma.workPlan.findUnique({ where: { id } });

    if (!plan) {
      throw new NotFoundException(`WorkPlan ${id} not found`);
    }
    if (plan.status === 'cancelled') {
      throw new BadRequestException('Plan is already cancelled.');
    }
    if (plan.status === 'running') {
      throw new BadRequestException(
        'Cannot cancel a running plan. Stop it first.',
      );
    }

    return this.prisma.workPlan.update({
      where: { id },
      data: { status: 'cancelled' },
    });
  }
}
