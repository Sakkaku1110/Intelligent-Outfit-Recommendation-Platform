import pg from 'pg'

const { Pool } = pg

export const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: Number(process.env.POSTGRES_PORT || 5432),
  database: process.env.POSTGRES_DB || 'smart_wardrobe',
  user: process.env.POSTGRES_USER || 'wardrobe',
  password: process.env.POSTGRES_PASSWORD || 'change-me-db-password',
})

export async function initDb() {
  await pool.query(`
    create table if not exists wardrobe_items (
      id text primary key,
      name text not null,
      type text not null,
      color text not null default '未知',
      season text not null default '四季',
      material text,
      image_url text,
      location text,
      count integer not null default 0,
      confidence numeric,
      spectral_signature jsonb not null default '{}'::jsonb,
      source text not null default 'ss928',
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      last_seen_at timestamptz not null default now()
    );

    create index if not exists idx_wardrobe_items_type on wardrobe_items(type);
    create index if not exists idx_wardrobe_items_updated_at on wardrobe_items(updated_at desc);
  `)
}

export function toApiItem(row) {
  return {
    id: row.id,
    name: row.name,
    type: row.type,
    color: row.color,
    season: row.season,
    material: row.material,
    imageUrl: row.image_url,
    img: row.image_url,
    location: row.location,
    count: Number(row.count || 0),
    confidence: row.confidence === null ? null : Number(row.confidence),
    spectralSignature: row.spectral_signature || {},
    source: row.source,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    lastSeenAt: row.last_seen_at,
  }
}
