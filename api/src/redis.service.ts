import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleDestroy {
  private client: Redis;

  constructor(private config: ConfigService) {
    const host = this.config.get('REDIS_HOST', 'localhost');
    const port = this.config.get('REDIS_PORT', 6379);
    const password = this.config.get('REDIS_PASSWORD', '');

    this.client = new Redis({
      host,
      port: Number(port),
      password: password || undefined,
      lazyConnect: true,
    });
  }

  async publish(channel: string, message: string): Promise<void> {
    await this.client.connect().catch(() => {});
    await this.client.publish(channel, message);
  }

  async onModuleDestroy() {
    await this.client.quit();
  }
}
