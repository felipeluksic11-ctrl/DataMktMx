import { Module } from '@nestjs/common';
import { PortalsController } from './portals.controller';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [PortalsController],
  providers: [PrismaService],
})
export class PortalsModule {}
