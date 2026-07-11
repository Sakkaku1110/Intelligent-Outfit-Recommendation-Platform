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
const llmInferenceUrl = (process.env.LLM_INFERENCE_URL || '').trim()
const llmApiKey = (process.env.LLM_API_KEY || process.env.CLOUD_API_KEY || '').trim()
const llmModel = (process.env.LLM_MODEL || 'outfit-lora-adapter').trim()
const llmFallbackEnabled = String(process.env.LLM_FALLBACK ?? 'true').toLowerCase() !== 'false'

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

function splitTags(value) {
  if (Array.isArray(value)) return value.map(item => String(item).trim()).filter(Boolean)
  return String(value || '').replace(/，/g, ',').replace(/、/g, ',').split(',').map(item => item.trim()).filter(Boolean)
}

function normalizeCategory(value) {
  const text = String(value || '').trim().toLowerCase()
  const aliases = {
    top: 'top',
    shirt: 'top',
    tshirt: 'top',
    tee: 'top',
    上衣: 'top',
    衬衫: 'top',
    短袖: 'top',
    卫衣: 'top',
    bottom: 'bottom',
    pants: 'bottom',
    trousers: 'bottom',
    skirt: 'bottom',
    下装: 'bottom',
    裤子: 'bottom',
    长裤: 'bottom',
    短裤: 'bottom',
    outer: 'outer',
    coat: 'outer',
    jacket: 'outer',
    outerwear: 'outer',
    外套: 'outer',
    shoes: 'shoes',
    shoe: 'shoes',
    鞋: 'shoes',
    鞋子: 'shoes',
    accessory: 'accessory',
    accessories: 'accessory',
    配饰: 'accessory',
  }
  return aliases[text] || text || 'top'
}

function compactWardrobeItem(item) {
  return {
    id: String(item.id || item.local_id || item.name || nanoid(8)),
    name: String(item.name || item.title || '未命名单品').slice(0, 120),
    category: normalizeCategory(item.category || item.type),
    color: item.color || item.color_label || 'unknown',
    material: item.material || '',
    season: item.season || 'all',
    occasion: item.occasion || 'all',
    warmth: Number.isFinite(Number(item.warmth)) ? Number(item.warmth) : 3,
    formality: Number.isFinite(Number(item.formality)) ? Number(item.formality) : 2,
    favorite_score: Number.isFinite(Number(item.favorite_score ?? item.favoriteScore)) ? Number(item.favorite_score ?? item.favoriteScore) : 3,
    wear_count: Number.isFinite(Number(item.wear_count ?? item.count)) ? Number(item.wear_count ?? item.count) : 0,
    image_url: item.image_url || item.imageUrl || item.img || '',
    display_image_url: item.display_image_url || item.displayImageUrl || '',
  }
}

function targetWarmth(tempC) {
  if (tempC <= 6) return 5
  if (tempC <= 14) return 4
  if (tempC <= 22) return 3
  if (tempC <= 29) return 2
  return 1
}

function seasonForTemperature(tempC) {
  if (tempC <= 10) return 'winter'
  if (tempC <= 22) return 'spring_autumn'
  if (tempC <= 29) return 'summer_light'
  return 'summer_hot'
}

function scoreItem(item, tempC, target, season, occasion) {
  const seasons = new Set(splitTags(item.season))
  const occasions = new Set(splitTags(item.occasion))
  const warmth = Math.max(1, Math.min(5, Number(item.warmth || 3)))
  const favorite = Math.max(1, Math.min(5, Number(item.favorite_score || 3)))
  let score = 40 - Math.abs(warmth - target) * 8 + favorite * 2 - Number(item.wear_count || 0) * 0.4
  const reason = []
  if (Math.abs(warmth - target) <= 1) {
    score += 12
    reason.push(`${item.name} 的保暖值适合当前温度`)
  }
  if (seasons.has(season) || seasons.has('all') || seasons.has('四季')) {
    score += 10
    reason.push(`${item.name} 的季节标签匹配`)
  }
  if (occasions.has(occasion) || occasions.has('all') || occasions.has('通用')) {
    score += 14
    reason.push(`${item.name} 适合 ${occasion} 场景`)
  }
  return { score, reason }
}

function colorScore(items) {
  const colors = items.map(item => String(item.color || '').toLowerCase()).filter(Boolean)
  if (!colors.length) return { score: 0, reason: '颜色信息不足，暂不作为主要依据' }
  const unique = new Set(colors)
  const neutral = colors.filter(color => ['black', 'white', 'gray', 'grey', 'navy', 'beige', '黑色', '白色', '灰色', '藏青色', '米色'].some(token => color.includes(token)))
  if (neutral.length >= Math.max(1, colors.length - 1)) return { score: 10, reason: '整体颜色以基础色为主，搭配冲突较低' }
  if (unique.size <= 2) return { score: 7, reason: '颜色数量较少，视觉上更统一' }
  if (unique.size >= 4) return { score: -8, reason: '颜色种类偏多，已降低推荐分' }
  return { score: 2, reason: '颜色搭配处于可接受范围' }
}

function localOutfitRecommendation(payload) {
  const wardrobe = Array.isArray(payload.wardrobe) ? payload.wardrobe.map(compactWardrobeItem) : []
  const weather = payload.weather && typeof payload.weather === 'object' ? payload.weather : {}
  const occasion = String(payload.occasion || 'school')
  const tempC = Number(weather.temperature_c ?? weather.temperatureC ?? 26)
  const target = targetWarmth(tempC)
  const season = seasonForTemperature(tempC)
  const required = ['top', 'bottom', 'shoes']
  if (tempC < 20) required.push('outer')
  const grouped = new Map()
  for (const item of wardrobe) {
    const category = normalizeCategory(item.category)
    const scored = scoreItem(item, tempC, target, season, occasion)
    const entry = { ...scored, item }
    grouped.set(category, [...(grouped.get(category) || []), entry])
  }
  for (const [category, values] of grouped.entries()) {
    grouped.set(category, values.sort((a, b) => b.score - a.score).slice(0, 4))
  }
  const active = required.filter(category => grouped.has(category))
  if (!active.includes('accessory') && grouped.has('accessory')) active.push('accessory')
  const missing = required.filter(category => !grouped.has(category))
  const combos = []
  function visit(index, selected) {
    if (index >= active.length) {
      const items = selected.map(entry => entry.item)
      const color = colorScore(items)
      const score = Math.round((selected.reduce((sum, entry) => sum + entry.score, 0) + color.score) * 10) / 10
      const reason = [
        `当前温度 ${tempC.toFixed(1)}°C，目标保暖值为 ${target}/5`,
        `场景为 ${occasion}，优先选择场景标签匹配的衣物`,
        color.reason,
        ...selected.flatMap(entry => entry.reason.slice(0, 2)),
      ]
      combos.push({
        score,
        items,
        reason: [...new Set(reason)].slice(0, 8),
        summary: `${tempC.toFixed(1)}°C / ${occasion}：${items.map(item => item.name).join(' + ')}`,
      })
      return
    }
    for (const entry of grouped.get(active[index]) || []) visit(index + 1, [...selected, entry])
  }
  if (active.length) visit(0, [])
  combos.sort((a, b) => b.score - a.score)
  return {
    weather,
    occasion,
    target_warmth: target,
    season_hint: season,
    missing_categories: missing,
    recommendations: combos.slice(0, Number(payload.limit || 3)),
    explain: [
      '云端 LLM 接口当前使用规则兼容兜底，可直接替换为 LoRA 推理服务。',
      '返回结构与 SS928 /api/recommendations 保持一致。',
    ],
  }
}

function enhanceLocalRecommendation(payload) {
  const local = payload.local_recommendation && typeof payload.local_recommendation === 'object'
    ? payload.local_recommendation
    : localOutfitRecommendation(payload)
  const recommendations = Array.isArray(local.recommendations) ? local.recommendations : []
  return {
    ...local,
    recommendations: recommendations.map((recommendation, index) => ({
      ...recommendation,
      score: Number(recommendation.score || 0) + Math.max(0, 3 - index) * 0.1,
      reason: [
        ...new Set([
          ...(Array.isArray(recommendation.reason) ? recommendation.reason : []),
          '大模型接口已接收衣柜、天气、场景和偏好输入；当前为可部署 mock/兜底推理。',
        ]),
      ].slice(0, 8),
      llm_rank: index + 1,
    })),
    source: 'cloud_llm_mock',
    model: llmModel,
    explain: [
      '云端大模型接口已打通；配置 LLM_INFERENCE_URL 后会转发到真实 LoRA/模型推理服务。',
      ...(Array.isArray(local.explain) ? local.explain : []),
    ].slice(0, 6),
  }
}

async function callLLMInference(payload) {
  if (!llmInferenceUrl) return enhanceLocalRecommendation(payload)
  const response = await fetch(llmInferenceUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(llmApiKey ? { Authorization: `Bearer ${llmApiKey}`, 'x-api-key': llmApiKey } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`LLM inference failed with HTTP ${response.status}`)
  }
  const result = await response.json()
  if (!result || typeof result !== 'object') {
    throw new Error('LLM inference returned a non-object response')
  }
  return {
    ...result,
    source: result.source || 'llm_inference_url',
    model: result.model || llmModel,
  }
}

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'smart-wardrobe-cloud',
    time: new Date().toISOString(),
    llm: {
      configured: Boolean(llmInferenceUrl),
      mode: llmInferenceUrl ? 'http_forward' : 'mock_fallback',
      model: llmModel,
      fallback: llmFallbackEnabled,
    },
  })
})

app.get('/api/llm/status', (_req, res) => {
  res.json({
    llm: {
      configured: Boolean(llmInferenceUrl),
      mode: llmInferenceUrl ? 'http_forward' : 'mock_fallback',
      model: llmModel,
      fallback: llmFallbackEnabled,
    },
  })
})

app.post('/api/llm/recommend', requireWriteKey, async (req, res, next) => {
  try {
    const payload = req.body && typeof req.body === 'object' ? req.body : {}
    if (!Array.isArray(payload.wardrobe) && !payload.local_recommendation) {
      return res.status(400).json({ error: 'wardrobe or local_recommendation is required' })
    }
    const started = Date.now()
    try {
      const result = await callLLMInference(payload)
      res.json({
        ok: true,
        ...result,
        llm: {
          status: llmInferenceUrl ? 'enhanced' : 'mock',
          mode: llmInferenceUrl ? 'http_forward' : 'mock_fallback',
          model: result.model || llmModel,
          elapsed_ms: Date.now() - started,
        },
      })
    } catch (error) {
      if (!llmFallbackEnabled) throw error
      const fallback = enhanceLocalRecommendation(payload)
      res.json({
        ok: true,
        ...fallback,
        llm: {
          status: 'fallback',
          mode: 'mock_fallback',
          model: llmModel,
          error: String(error.message || error).slice(0, 300),
          elapsed_ms: Date.now() - started,
        },
      })
    }
  } catch (error) {
    next(error)
  }
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
