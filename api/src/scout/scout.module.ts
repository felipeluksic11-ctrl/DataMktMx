import { Module } from '@nestjs/common';
import { ScoutController } from './scout.controller';

@Module({
  controllers: [ScoutController],
})
export class ScoutModule {}
