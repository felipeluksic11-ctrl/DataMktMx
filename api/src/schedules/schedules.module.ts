import { Module } from '@nestjs/common';
import { SchedulesController } from './schedules.controller';
import { PrismaService } from '../prisma.service';
import { RedisService } from '../redis.service';

@Module({
  controllers: [SchedulesController],
  providers: [PrismaService, RedisService],
})
export class SchedulesModule {}
