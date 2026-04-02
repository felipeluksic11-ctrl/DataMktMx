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
    const take = Math.min(parseInt(limit || '20', 10), 1000);
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
        r.id, p.slug as "portalSlug",
        r.external_id as "externalId", r.internal_code as "internalCode",
        r.title, r.description, r.operation, r.property_type as "propertyType",
        r.price, r.currency, r.maintenance_fee as "maintenanceFee",
        r.street_and_number as "streetAndNumber",
        r.neighborhood, r.city, r.municipality, r.state, r.country,
        r.zip_code as "zipCode",
        r.bedrooms, r.bathrooms, r.half_bathrooms as "halfBathrooms",
        r.parking_spaces as "parkingSpaces",
        r.land_m2 as "landM2", r.construction_m2 as "constructionM2",
        r.antiquity, r.construction_years as "constructionYears",
        r.conservation_status as "conservationStatus",
        r.has_balcony as "hasBalcony", r.has_elevator as "hasElevator",
        r.has_storage as "hasStorage", r.built_levels as "builtLevels",
        r.images_count as "imagesCount",
        r.url_listing as "urlListing",
        r.first_seen_at as "firstSeenAt", r.last_seen_at as "lastSeenAt",
        r.created_at as "createdAt"
      FROM raw.raw_listings r
      JOIN public.portals p ON r.portal_id = p.id
      WHERE ${whereClause}
      ORDER BY r.created_at DESC NULLS LAST
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

  @Get('quality')
  async quality() {
    const [fillRatesResult, byPortalResult, timeResult] = await Promise.all([
      this.prisma.$queryRaw<[Record<string, unknown>]>`
        SELECT
          COUNT(*) as total,
          ROUND(100.0 * COUNT(price) / NULLIF(COUNT(*), 0), 1) as price,
          ROUND(100.0 * COUNT(bedrooms) / NULLIF(COUNT(*), 0), 1) as bedrooms,
          ROUND(100.0 * COUNT(bathrooms) / NULLIF(COUNT(*), 0), 1) as bathrooms,
          ROUND(100.0 * COUNT(land_m2) / NULLIF(COUNT(*), 0), 1) as land_m2,
          ROUND(100.0 * COUNT(construction_m2) / NULLIF(COUNT(*), 0), 1) as construction_m2,
          ROUND(100.0 * COUNT(neighborhood) / NULLIF(COUNT(*), 0), 1) as neighborhood,
          ROUND(100.0 * COUNT(state) / NULLIF(COUNT(*), 0), 1) as state,
          ROUND(100.0 * COUNT(municipality) / NULLIF(COUNT(*), 0), 1) as municipality,
          ROUND(100.0 * COUNT(parking_spaces) / NULLIF(COUNT(*), 0), 1) as parking_spaces,
          ROUND(100.0 * COUNT(property_type) / NULLIF(COUNT(*), 0), 1) as property_type,
          ROUND(100.0 * COUNT(operation) / NULLIF(COUNT(*), 0), 1) as operation
        FROM raw.raw_listings`,
      this.prisma.$queryRaw<Record<string, unknown>[]>`
        SELECT
          p.name as portal_name, p.slug as portal_slug, p.is_active as is_active,
          COUNT(*) as listing_count,
          ROUND(100.0 * COUNT(r.price) / NULLIF(COUNT(*), 0), 1) as price_fill,
          ROUND(100.0 * COUNT(r.bedrooms) / NULLIF(COUNT(*), 0), 1) as bedrooms_fill,
          ROUND(100.0 * COUNT(r.bathrooms) / NULLIF(COUNT(*), 0), 1) as bathrooms_fill,
          ROUND(100.0 * COUNT(r.construction_m2) / NULLIF(COUNT(*), 0), 1) as m2_fill,
          ROUND(100.0 * COUNT(r.neighborhood) / NULLIF(COUNT(*), 0), 1) as neighborhood_fill
        FROM raw.raw_listings r
        JOIN public.portals p ON r.portal_id = p.id
        GROUP BY p.name, p.slug, p.is_active
        ORDER BY COUNT(*) DESC`,
      this.prisma.$queryRaw<[{ today: bigint; week: bigint }]>`
        SELECT
          COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today,
          COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as week
        FROM raw.raw_listings`,
    ]);

    const fr = fillRatesResult[0];
    const fields = ['price', 'bedrooms', 'bathrooms', 'land_m2', 'construction_m2',
      'neighborhood', 'state', 'municipality', 'parking_spaces', 'property_type', 'operation'];
    const fillRates: Record<string, number> = {};
    let sum = 0;
    for (const f of fields) {
      const val = Number(fr[f] || 0);
      fillRates[f] = val;
      sum += val;
    }

    return {
      listingsToday: Number(timeResult[0].today),
      listingsThisWeek: Number(timeResult[0].week),
      fillRates,
      overallCompleteness: Math.round(sum / fields.length),
      byPortal: byPortalResult.map((r) => ({
        portalName: r.portal_name,
        portalSlug: r.portal_slug,
        isActive: r.is_active,
        listingCount: Number(r.listing_count),
        priceFill: Number(r.price_fill),
        bedroomsFill: Number(r.bedrooms_fill),
        bathroomsFill: Number(r.bathrooms_fill),
        m2Fill: Number(r.m2_fill),
        neighborhoodFill: Number(r.neighborhood_fill),
      })),
    };
  }

  @Get('ai-usage')
  async aiUsage() {
    // Read usage from shared DB table
    try {
      const result = await this.prisma.$queryRawUnsafe<Record<string, unknown>[]>(`
        SELECT * FROM public.ai_usage ORDER BY created_at DESC LIMIT 1
      `);
      if (result.length > 0) {
        const row = result[0];
        return {
          totalCalls: Number(row.total_calls || 0),
          totalCostUsd: Number(row.total_cost_usd || 0),
          todayCostUsd: Number(row.today_cost_usd || 0),
          byPurpose: row.by_purpose || {},
        };
      }
    } catch {}
    return { totalCalls: 0, totalCostUsd: 0, todayCostUsd: 0, byPurpose: {} };
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
