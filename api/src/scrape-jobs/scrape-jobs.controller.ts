import {
  Controller,
  Get,
  Param,
  Query,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Controller('scrape-jobs')
export class ScrapeJobsController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async findAll(
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('portalId') portalId?: string,
    @Query('status') status?: string,
  ) {
    const take = Math.min(parseInt(limit || '20', 10), 100);
    const skip = (Math.max(parseInt(page || '1', 10), 1) - 1) * take;

    const where: Record<string, unknown> = {};
    if (portalId) where.portalId = portalId;
    if (status) where.status = status;

    const [jobs, total] = await Promise.all([
      this.prisma.scrapeJob.findMany({
        where,
        include: {
          portal: { select: { name: true, slug: true } },
        },
        orderBy: { createdAt: 'desc' },
        take,
        skip,
      }),
      this.prisma.scrapeJob.count({ where }),
    ]);

    return { data: jobs, total, page: Math.floor(skip / take) + 1, limit: take };
  }

  @Get(':id')
  async findOne(@Param('id') id: string) {
    const job = await this.prisma.scrapeJob.findUnique({
      where: { id },
      include: {
        portal: { select: { name: true, slug: true } },
      },
    });

    if (!job) {
      throw new NotFoundException(`ScrapeJob ${id} not found`);
    }

    return job;
  }
}
