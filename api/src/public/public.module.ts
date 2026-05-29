import { Module } from '@nestjs/common';
import { PublicController } from './public.controller';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [PublicController],
  providers: [PrismaService],
})
export class PublicModule {}
