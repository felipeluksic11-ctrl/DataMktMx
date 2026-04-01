import {
  Controller,
  Get,
  Query,
  Res,
} from '@nestjs/common';
import { Response } from 'express';
import { PrismaService } from '../prisma.service';
import { Prisma } from '@prisma/client';

@Controller('data')
export class DataController {
  constructor(private readonly prisma: PrismaService) {}

  @Get('listings')
  async listings(
    @Res({ passthrough: true }) res: Response,
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('operation') operation?: string,
    @Query('propertyType') propertyType?: string,
    @Query('state') state?: string,
    @Query('municipality') municipality?: string,
    @Query('priceMin') priceMin?: string,
    @Query('priceMax') priceMax?: string,
  ) {
    const take = Math.min(parseInt(limit || '20', 10), 100);
    const skip = (Math.max(parseInt(page || '1', 10), 1) - 1) * take;

    const conditions: string[] = ['1=1'];
    const params: unknown[] = [];
    let paramIdx = 1;

    if (operation) {
      conditions.push(`operation = $${paramIdx++}`);
      params.push(operation);
    }
    if (propertyType) {
      conditions.push(`property_type = $${paramIdx++}`);
      params.push(propertyType);
    }
    if (state) {
      conditions.push(`state = $${paramIdx++}`);
      params.push(state);
    }
    if (municipality) {
      conditions.push(`municipality = $${paramIdx++}`);
      params.push(municipality);
    }
    if (priceMin) {
      conditions.push(`price >= $${paramIdx++}`);
      params.push(parseFloat(priceMin));
    }
    if (priceMax) {
      conditions.push(`price <= $${paramIdx++}`);
      params.push(parseFloat(priceMax));
    }

    const whereClause = conditions.join(' AND ');

    const countResult = await this.prisma.$queryRawUnsafe<[{ count: bigint }]>(
      `SELECT COUNT(*) as count FROM raw.raw_listings WHERE ${whereClause}`,
      ...params,
    );
    const total = Number(countResult[0].count);

    const rows = await this.prisma.$queryRawUnsafe(
      `SELECT
        id, portal_id as "portalId", external_id as "externalId",
        title, operation, property_type as "propertyType",
        price, currency, state, municipality, city, neighborhood,
        street_and_number as "streetAndNumber",
        bedrooms, bathrooms, half_bathrooms as "halfBathrooms",
        parking_spaces as "parkingSpaces",
        land_m2 as "landM2", construction_m2 as "constructionM2",
        antiquity, conservation_status as "conservationStatus",
        images_count as "imagesCount",
        url_listing as "urlListing",
        first_seen_at as "firstSeenAt", last_seen_at as "lastSeenAt",
        created_at as "createdAt"
      FROM raw.raw_listings
      WHERE ${whereClause}
      ORDER BY created_at DESC NULLS LAST
      LIMIT $${paramIdx++} OFFSET $${paramIdx++}`,
      ...params,
      take,
      skip,
    );

    res.header('X-Total-Count', String(total));

    return {
      data: rows,
      total,
      page: Math.floor(skip / take) + 1,
      limit: take,
    };
  }

  @Get('stats')
  async stats() {
    const [totalResult, byOperation, byState, byPropertyType, avgPriceByState] =
      await Promise.all([
        this.prisma.$queryRaw<[{ count: bigint }]>`
          SELECT COUNT(*) as count FROM raw.raw_listings`,
        this.prisma.$queryRaw<{ operation: string; count: bigint }[]>`
          SELECT operation, COUNT(*) as count
          FROM raw.raw_listings
          WHERE operation IS NOT NULL
          GROUP BY operation
          ORDER BY count DESC`,
        this.prisma.$queryRaw<{ state: string; count: bigint }[]>`
          SELECT state, COUNT(*) as count
          FROM raw.raw_listings
          WHERE state IS NOT NULL
          GROUP BY state
          ORDER BY count DESC
          LIMIT 20`,
        this.prisma.$queryRaw<{ property_type: string; count: bigint }[]>`
          SELECT property_type, COUNT(*) as count
          FROM raw.raw_listings
          WHERE property_type IS NOT NULL
          GROUP BY property_type
          ORDER BY count DESC`,
        this.prisma.$queryRaw<{ state: string; avg_price: number }[]>`
          SELECT state, ROUND(AVG(price)::numeric, 2) as avg_price
          FROM raw.raw_listings
          WHERE state IS NOT NULL AND price IS NOT NULL
          GROUP BY state
          ORDER BY avg_price DESC
          LIMIT 20`,
      ]);

    return {
      totalListings: Number(totalResult[0].count),
      byOperation: byOperation.map((r) => ({
        operation: r.operation,
        count: Number(r.count),
      })),
      byState: byState.map((r) => ({
        state: r.state,
        count: Number(r.count),
      })),
      byPropertyType: byPropertyType.map((r) => ({
        propertyType: r.property_type,
        count: Number(r.count),
      })),
      avgPriceByState: avgPriceByState.map((r) => ({
        state: r.state,
        avgPrice: Number(r.avg_price),
      })),
    };
  }

  @Get('export')
  async exportCsv(
    @Res() res: Response,
    @Query('operation') operation?: string,
    @Query('propertyType') propertyType?: string,
    @Query('state') state?: string,
    @Query('municipality') municipality?: string,
    @Query('priceMin') priceMin?: string,
    @Query('priceMax') priceMax?: string,
  ) {
    const conditions: string[] = ['1=1'];
    const params: unknown[] = [];
    let paramIdx = 1;

    if (operation) {
      conditions.push(`operation = $${paramIdx++}`);
      params.push(operation);
    }
    if (propertyType) {
      conditions.push(`property_type = $${paramIdx++}`);
      params.push(propertyType);
    }
    if (state) {
      conditions.push(`state = $${paramIdx++}`);
      params.push(state);
    }
    if (municipality) {
      conditions.push(`municipality = $${paramIdx++}`);
      params.push(municipality);
    }
    if (priceMin) {
      conditions.push(`price >= $${paramIdx++}`);
      params.push(parseFloat(priceMin));
    }
    if (priceMax) {
      conditions.push(`price <= $${paramIdx++}`);
      params.push(parseFloat(priceMax));
    }

    const whereClause = conditions.join(' AND ');

    const rows = await this.prisma.$queryRawUnsafe<Record<string, unknown>[]>(
      `SELECT
        id, external_id, title, operation, property_type,
        price, currency, state, municipality, city, neighborhood,
        bedrooms, bathrooms, land_m2, construction_m2,
        images_count, created_at
      FROM raw.raw_listings
      WHERE ${whereClause}
      ORDER BY price DESC NULLS LAST
      LIMIT 50000`,
      ...params,
    );

    res.header('Content-Type', 'text/csv; charset=utf-8');
    res.header(
      'Content-Disposition',
      `attachment; filename="listings_${new Date().toISOString().slice(0, 10)}.csv"`,
    );

    if (rows.length === 0) {
      res.send('');
      return;
    }

    const headers = Object.keys(rows[0]);
    const csvLines = [headers.join(',')];

    for (const row of rows) {
      const values = headers.map((h) => {
        const val = row[h];
        if (val === null || val === undefined) return '';
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      });
      csvLines.push(values.join(','));
    }

    res.send(csvLines.join('\n'));
  }
}
