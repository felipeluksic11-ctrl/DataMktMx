import { Controller, Get, Param } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Controller('public')
export class PublicController {
  constructor(private readonly prisma: PrismaService) {}

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
          ORDER BY count DESC`,
        this.prisma.$queryRaw<{ property_type: string; count: bigint }[]>`
          SELECT property_type, COUNT(*) as count
          FROM raw.raw_listings
          WHERE property_type IS NOT NULL
          GROUP BY property_type
          ORDER BY count DESC`,
        this.prisma.$queryRaw<{ state: string; avg_price: number }[]>`
          SELECT state, ROUND(AVG(price)::numeric, 0) as avg_price
          FROM raw.raw_listings
          WHERE state IS NOT NULL AND price IS NOT NULL AND price > 0
          GROUP BY state
          ORDER BY avg_price DESC`,
      ]);

    return {
      totalListings: Number(totalResult[0].count),
      statesCovered: byState.length,
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

  @Get('stats/:state')
  async statsByState(@Param('state') state: string) {
    const [totalResult, byMunicipality, byPropertyType, priceStats] =
      await Promise.all([
        this.prisma.$queryRaw<[{ count: bigint }]>`
          SELECT COUNT(*) as count
          FROM raw.raw_listings
          WHERE LOWER(state) = LOWER(${state})`,
        this.prisma.$queryRaw<{ municipality: string; count: bigint }[]>`
          SELECT municipality, COUNT(*) as count
          FROM raw.raw_listings
          WHERE LOWER(state) = LOWER(${state}) AND municipality IS NOT NULL
          GROUP BY municipality
          ORDER BY count DESC
          LIMIT 30`,
        this.prisma.$queryRaw<{ property_type: string; count: bigint }[]>`
          SELECT property_type, COUNT(*) as count
          FROM raw.raw_listings
          WHERE LOWER(state) = LOWER(${state}) AND property_type IS NOT NULL
          GROUP BY property_type
          ORDER BY count DESC`,
        this.prisma.$queryRaw<
          [{ avg_price: number; min_price: number; max_price: number; median_price: number }]
        >`
          SELECT
            ROUND(AVG(price)::numeric, 0) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)::numeric, 0) as median_price
          FROM raw.raw_listings
          WHERE LOWER(state) = LOWER(${state}) AND price IS NOT NULL AND price > 0`,
      ]);

    const total = Number(totalResult[0].count);
    if (total === 0) {
      return { state, totalListings: 0, byMunicipality: [], byPropertyType: [], priceStats: null };
    }

    return {
      state,
      totalListings: total,
      byMunicipality: byMunicipality.map((r) => ({
        municipality: r.municipality,
        count: Number(r.count),
      })),
      byPropertyType: byPropertyType.map((r) => ({
        propertyType: r.property_type,
        count: Number(r.count),
      })),
      priceStats: {
        avgPrice: Number(priceStats[0].avg_price),
        minPrice: Number(priceStats[0].min_price),
        maxPrice: Number(priceStats[0].max_price),
        medianPrice: Number(priceStats[0].median_price),
      },
    };
  }

  @Get('filters')
  async filters() {
    const [states, propertyTypes, operations] = await Promise.all([
      this.prisma.$queryRaw<{ state: string; count: bigint }[]>`
        SELECT state, COUNT(*) as count
        FROM raw.raw_listings
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY state`,
      this.prisma.$queryRaw<{ property_type: string; count: bigint }[]>`
        SELECT property_type, COUNT(*) as count
        FROM raw.raw_listings
        WHERE property_type IS NOT NULL
        GROUP BY property_type
        ORDER BY count DESC`,
      this.prisma.$queryRaw<{ operation: string; count: bigint }[]>`
        SELECT operation, COUNT(*) as count
        FROM raw.raw_listings
        WHERE operation IS NOT NULL
        GROUP BY operation
        ORDER BY count DESC`,
    ]);

    return {
      states: states.map((r) => ({ value: r.state, count: Number(r.count) })),
      propertyTypes: propertyTypes.map((r) => ({ value: r.property_type, count: Number(r.count) })),
      operations: operations.map((r) => ({ value: r.operation, count: Number(r.count) })),
    };
  }
}
