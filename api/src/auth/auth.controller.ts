import { Body, Controller, Post, HttpException, HttpStatus } from '@nestjs/common';
import { createHash } from 'crypto';
import { ConfigService } from '@nestjs/config';

@Controller('auth')
export class AuthController {
  constructor(private config: ConfigService) {}

  @Post('login')
  async login(@Body() body: { password: string }) {
    const adminPassword = this.config.get<string>('ADMIN_PASSWORD');

    if (!adminPassword) {
      throw new HttpException('ADMIN_PASSWORD not configured', HttpStatus.INTERNAL_SERVER_ERROR);
    }

    if (!body.password) {
      throw new HttpException('Password required', HttpStatus.BAD_REQUEST);
    }

    // Simple password check (not user-based, single admin)
    const hash = createHash('sha256').update(body.password).digest('hex');
    const expectedHash = createHash('sha256').update(adminPassword).digest('hex');

    if (hash !== expectedHash) {
      throw new HttpException('Invalid password', HttpStatus.UNAUTHORIZED);
    }

    // Return a simple session token (hash of password + date)
    const token = createHash('sha256')
      .update(`${adminPassword}-${new Date().toISOString().split('T')[0]}`)
      .digest('hex');

    return { token, expiresIn: '24h' };
  }

  @Post('verify')
  async verify(@Body() body: { token: string }) {
    const adminPassword = this.config.get<string>('ADMIN_PASSWORD');
    if (!adminPassword || !body.token) {
      throw new HttpException('Invalid token', HttpStatus.UNAUTHORIZED);
    }

    const expectedToken = createHash('sha256')
      .update(`${adminPassword}-${new Date().toISOString().split('T')[0]}`)
      .digest('hex');

    if (body.token !== expectedToken) {
      throw new HttpException('Invalid or expired token', HttpStatus.UNAUTHORIZED);
    }

    return { valid: true };
  }
}
