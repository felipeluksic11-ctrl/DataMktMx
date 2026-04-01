import {
  Controller,
  Post,
  Body,
  BadRequestException,
  InternalServerErrorException,
} from '@nestjs/common';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

@Controller('scout')
export class ScoutController {
  @Post('run')
  async run(
    @Body() body: { portalSlug: string; operation: string; states?: string[] },
  ) {
    const { portalSlug, operation } = body;

    if (!portalSlug || !operation) {
      throw new BadRequestException(
        'portalSlug and operation are required.',
      );
    }

    // Validate inputs to prevent injection
    if (!/^[a-z0-9_-]+$/.test(portalSlug)) {
      throw new BadRequestException('Invalid portalSlug format.');
    }
    if (!/^[a-z_]+$/.test(operation)) {
      throw new BadRequestException('Invalid operation format.');
    }

    const pythonCode = [
      'import asyncio, json',
      'from orchestrator.scouts import SCOUT_REGISTRY',
      `scout = SCOUT_REGISTRY['${portalSlug}']()`,
      `report = asyncio.run(scout.run('${operation}'))`,
      'print(json.dumps(report.to_dict()))',
    ].join('; ');

    const command = `cd /Users/felipesolarluksic/Beta3.1/src && /Users/felipesolarluksic/Beta3.1/.venv/bin/python -c "${pythonCode}"`;

    try {
      const { stdout, stderr } = await execAsync(command, {
        timeout: 120_000,
      });

      if (stderr) {
        console.warn('Scout stderr:', stderr);
      }

      try {
        return JSON.parse(stdout.trim());
      } catch {
        throw new InternalServerErrorException(
          'Failed to parse scout output as JSON.',
        );
      }
    } catch (error: unknown) {
      const msg =
        error instanceof Error ? error.message : 'Unknown error';
      throw new InternalServerErrorException(
        `Scout execution failed: ${msg}`,
      );
    }
  }
}
