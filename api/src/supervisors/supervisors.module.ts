import { Module } from '@nestjs/common';
import { SupervisorsController } from './supervisors.controller';
import { PrismaService } from '../prisma.service';
import { RedisService } from '../redis.service';

@Module({
  controllers: [SupervisorsController],
  providers: [PrismaService, RedisService],
})
export class SupervisorsModule {}
