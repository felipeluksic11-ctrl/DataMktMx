import { Module } from '@nestjs/common';
import { ScrapeJobsController } from './scrape-jobs.controller';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [ScrapeJobsController],
  providers: [PrismaService],
})
export class ScrapeJobsModule {}
