import {
  Controller,
  Get,
  Patch,
  Param,
  Body,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Controller('portals')
export class PortalsController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async findAll() {
    const portals = await this.prisma.portal.findMany({
      include: {
        scrapeJobs: {
          orderBy: { createdAt: 'desc' },
          take: 1,
          select: { id: true, status: true, createdAt: true },
        },
        _count: { select: { scrapeJobs: true } },
      },
      orderBy: { name: 'asc' },
    });

    return portals.map((p) => ({
      id: p.id,
      name: p.name,
      slug: p.slug,
      baseUrl: p.baseUrl,
      scraperModule: p.scraperModule,
      isActive: p.isActive,
      avgListings: p.avgListings,
      notes: p.notes,
      createdAt: p.createdAt,
      updatedAt: p.updatedAt,
      scrapeJobCount: p._count.scrapeJobs,
      latestJob: p.scrapeJobs[0] ?? null,
    }));
  }

  @Get(':id')
  async findOne(@Param('id') id: string) {
    const portal = await this.prisma.portal.findUnique({
      where: { id },
      include: {
        scrapeJobs: {
          orderBy: { createdAt: 'desc' },
          take: 5,
        },
        workPlans: {
          orderBy: { createdAt: 'desc' },
          take: 5,
        },
        _count: {
          select: { scrapeJobs: true, workPlans: true },
        },
      },
    });

    if (!portal) {
      throw new NotFoundException(`Portal ${id} not found`);
    }

    return {
      ...portal,
      scrapeJobCount: portal._count.scrapeJobs,
      workPlanCount: portal._count.workPlans,
    };
  }

  @Patch(':id')
  async update(
    @Param('id') id: string,
    @Body() body: { isActive?: boolean; notes?: string },
  ) {
    const existing = await this.prisma.portal.findUnique({ where: { id } });
    if (!existing) {
      throw new NotFoundException(`Portal ${id} not found`);
    }

    const data: Record<string, unknown> = {};
    if (body.isActive !== undefined) data.isActive = body.isActive;
    if (body.notes !== undefined) data.notes = body.notes;

    return this.prisma.portal.update({ where: { id }, data });
  }
}
