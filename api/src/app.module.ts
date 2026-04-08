import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { HealthController } from './health.controller';
import { PortalsModule } from './portals/portals.module';
import { ScrapeJobsModule } from './scrape-jobs/scrape-jobs.module';
import { WorkPlansModule } from './work-plans/work-plans.module';
import { DataModule } from './data/data.module';
import { ScoutModule } from './scout/scout.module';
import { AuthModule } from './auth/auth.module';
import { SchedulesModule } from './schedules/schedules.module';
import { SupervisorsModule } from './supervisors/supervisors.module';
import { AuditModule } from './audit/audit.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    PortalsModule,
    ScrapeJobsModule,
    WorkPlansModule,
    DataModule,
    ScoutModule,
    AuthModule,
    SchedulesModule,
    SupervisorsModule,
    AuditModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}
