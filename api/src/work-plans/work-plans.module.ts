import { Module } from '@nestjs/common';
import { WorkPlansController } from './work-plans.controller';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [WorkPlansController],
  providers: [PrismaService],
})
export class WorkPlansModule {}
