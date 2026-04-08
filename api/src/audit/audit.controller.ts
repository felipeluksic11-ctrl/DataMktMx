import { Controller, Get, Query } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Controller('audit')
export class AuditController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async findAll(
    @Query('page') page = '1',
    @Query('limit') limit = '30',
    @Query('entityType') entityType?: string,
    @Query('action') action?: string,
    @Query('actor') actor?: string,
    @Query('isAutomatic') isAutomatic?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
  ) {
    const skip = (Number(page) - 1) * Number(limit);
    const where: Record<string, unknown> = {};

    if (entityType) where.entityType = entityType;
    if (action) where.action = action;
    if (actor) where.actor = actor;
    if (isAutomatic !== undefined) where.isAutomatic = isAutomatic === 'true';
    if (from || to) {
      where.createdAt = {};
      if (from) (where.createdAt as Record<string, unknown>).gte = new Date(from);
      if (to) (where.createdAt as Record<string, unknown>).lte = new Date(to);
    }

    const [entries, total] = await Promise.all([
      this.prisma.auditLog.findMany({
        where,
        orderBy: { createdAt: 'desc' },
        skip,
        take: Number(limit),
      }),
      this.prisma.auditLog.count({ where }),
    ]);

    return { data: entries, total, page: Number(page), limit: Number(limit) };
  }

  @Get('timeline')
  async timeline(@Query('days') days = '7') {
    const since = new Date();
    since.setDate(since.getDate() - Number(days));

    const entries = await this.prisma.auditLog.findMany({
      where: { createdAt: { gte: since } },
      orderBy: { createdAt: 'desc' },
      take: 200,
    });

    // Group by date
    const grouped: Record<string, typeof entries> = {};
    for (const entry of entries) {
      const dateKey = entry.createdAt.toISOString().split('T')[0];
      if (!grouped[dateKey]) grouped[dateKey] = [];
      grouped[dateKey].push(entry);
    }

    return grouped;
  }

  @Get('search')
  async search(
    @Query('q') q: string,
    @Query('limit') limit = '30',
  ) {
    if (!q || q.length < 2) return { data: [], total: 0 };

    const entries = await this.prisma.auditLog.findMany({
      where: {
        summary: { contains: q, mode: 'insensitive' },
      },
      orderBy: { createdAt: 'desc' },
      take: Number(limit),
    });

    return { data: entries, total: entries.length };
  }
}
