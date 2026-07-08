import 'dotenv/config'
import cors from 'cors'
import express from 'express'
import multer from 'multer'
import { nanoid } from 'nanoid'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { initDb, pool, toApiItem } from './db.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const app = express()
const port = Number(process.env.PORT || 3000)
const publicBaseUrl = (process.env.PUBLIC_BASE_URL || `http://localhost:${port}`).replace(/\/$/, '')

const uploadDir = path.resolve(__dirname, '../uploads')
fs.mkdirSync(uploadDir, { recursive: true })
const storage = multer.diskStorage({
  destination: uploadDir,
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase() || '.jpg'
    cb(null, `${Date.now()}-${nanoid(8)}${ext}`)
  },
})
const upload = multer({
  storage,
  limits: { fileSize: 8 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    cb(null, file.mimetype.startsWith('image/'))
  },
})

const corsOrigin = process.env.CORS_ORIGIN || '*'
app.use(cors({
  origin: corsOrigin === '*' ? '*' : corsOrigin.split(',').map(item => item.trim()),
}))
app.use(express.json({ limit: '2mb' }))
app.use('/uploads', express.static(uploadDir))

function requireWriteKey(req, res, next) {
  const expected = process.env.CLOUD_API_KEY
  if (!expected) return next()
  const actual = req.header('x-api-key') || req.query.apiKey
  if (actual === expected) return next()
  return res.status(401).json({ error: 'invalid api key' })
}

function normalizeItemInput(body) {
  return {
    name: String(body.name || '').trim(),
    type: String(body.type || '').trim(),
    color: String(body.color || '未知').trim(),
    season: String(body.season || '四季').trim(),
    material: body.material ? String(body.material).trim() : null,
    imageUrl: body.imageUrl || body.img || null,
    location: body.location ? String(body.location).trim() : null,
    count: Number.isFinite(Number(body.count)) ? Number(body.count) : 0,
    confidence: body.confidence === undefined || body.confidence === null ? null : Number(body.confidence),
    spectralSignature: body.spectralSignature || body.spectral_signature || {},
    source: body.source ? String(body.source).trim() : 'ss928',
    lastSeenAt: body.lastSeenAt || body.last_seen_at || new Date().toISOString(),
  }
}

app.get('/health', (_req, res) => {
  res.json({ ok: true, service: 'smart-wardrobe-cloud', time: new Date().toISOString() })
})

app.get('/api/wardrobe/items', async (req, res, next) => {
  try {
    const { type, q } = req.query
    const values = []
    const where = []

    if (type) {
      values.push(String(type))
      where.push(`type = $${values.length}`)
    }
    if (q) {
      values.push(`%${String(q)}%`)
      where.push(`(name ilike $${values.length} or color ilike $${values.length} or season ilike $${values.length} or location ilike $${values.length})`)
    }

    const result = await pool.query(
      `select * from wardrobe_items ${where.length ? `where ${where.join(' and ')}` : ''} order by updated_at desc`,
      values
    )
    res.json({ items: result.rows.map(toApiItem) })
  } catch (error) {
    next(error)
  }
})

app.post('/api/wardrobe/items', requireWriteKey, async (req, res, next) => {
  try {
    const item = normalizeItemInput(req.body)
    if (!item.name || !item.type) {
      return res.status(400).json({ error: 'name and type are required' })
    }

    const id = req.body.id ? String(req.body.id) : `cloth_${nanoid(10)}`
    const result = await pool.query(`
      insert into wardrobe_items (
        id, name, type, color, season, material, image_url, location,
        count, confidence, spectral_signature, source, last_seen_at
      )
      values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13)
      on conflict (id) do update set
        name = excluded.name,
        type = excluded.type,
        color = excluded.color,
        season = excluded.season,
        material = excluded.material,
        image_url = coalesce(excluded.image_url, wardrobe_items.image_url),
        location = excluded.location,
        count = excluded.count,
        confidence = excluded.confidence,
        spectral_signature = excluded.spectral_signature,
        source = excluded.source,
        last_seen_at = excluded.last_seen_at,
        updated_at = now()
      returning *
    `, [
      id,
      item.name,
      item.type,
      item.color,
      item.season,
      item.material,
      item.imageUrl,
      item.location,
      item.count,
      item.confidence,
      JSON.stringify(item.spectralSignature),
      item.source,
      item.lastSeenAt,
    ])

    res.status(201).json({ item: toApiItem(result.rows[0]) })
  } catch (error) {
    next(error)
  }
})

app.patch('/api/wardrobe/items/:id', requireWriteKey, async (req, res, next) => {
  try {
    const existing = await pool.query('select * from wardrobe_items where id = $1', [req.params.id])
    if (!existing.rowCount) return res.status(404).json({ error: 'item not found' })

    const merged = normalizeItemInput({ ...toApiItem(existing.rows[0]), ...req.body })
    const result = await pool.query(`
      update wardrobe_items set
        name = $2,
        type = $3,
        color = $4,
        season = $5,
        material = $6,
        image_url = $7,
        location = $8,
        count = $9,
        confidence = $10,
        spectral_signature = $11::jsonb,
        source = $12,
        last_seen_at = $13,
        updated_at = now()
      where id = $1
      returning *
    `, [
      req.params.id,
      merged.name,
      merged.type,
      merged.color,
      merged.season,
      merged.material,
      merged.imageUrl,
      merged.location,
      merged.count,
      merged.confidence,
      JSON.stringify(merged.spectralSignature),
      merged.source,
      merged.lastSeenAt,
    ])

    res.json({ item: toApiItem(result.rows[0]) })
  } catch (error) {
    next(error)
  }
})

app.post('/api/wardrobe/items/:id/photo', requireWriteKey, upload.single('photo'), async (req, res, next) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'photo file is required' })
    const imageUrl = `${publicBaseUrl}/uploads/${req.file.filename}`
    const result = await pool.query(
      'update wardrobe_items set image_url = $2, updated_at = now() where id = $1 returning *',
      [req.params.id, imageUrl]
    )
    if (!result.rowCount) return res.status(404).json({ error: 'item not found' })
    res.json({ item: toApiItem(result.rows[0]) })
  } catch (error) {
    next(error)
  }
})

app.delete('/api/wardrobe/items/:id', requireWriteKey, async (req, res, next) => {
  try {
    const result = await pool.query('delete from wardrobe_items where id = $1 returning id', [req.params.id])
    if (!result.rowCount) return res.status(404).json({ error: 'item not found' })
    res.status(204).end()
  } catch (error) {
    next(error)
  }
})

app.use((error, _req, res, _next) => {
  console.error(error)
  res.status(500).json({ error: 'internal server error' })
})

await initDb()
app.listen(port, '0.0.0.0', () => {
  console.log(`Smart wardrobe cloud API listening on ${port}`)
})
