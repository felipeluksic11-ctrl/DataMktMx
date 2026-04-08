import { Module } from '@nestjs/common';
import { AuditController } from './audit.controller';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [AuditController],
  providers: [PrismaService],
})
export class AuditModule {}
