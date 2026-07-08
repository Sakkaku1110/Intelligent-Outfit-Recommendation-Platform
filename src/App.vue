<template>
  <div class="clothes-app-dark" :class="themeClass">
    <header class="app-header">
      <div class="brand">
        <i class="ri-cpu-line"></i>
        <span>ClothesAI <small>衣智柜</small></span>
      </div>
      <div class="header-status">
        <button class="theme-toggle" type="button" @click="toggleTheme">
          <i :class="themeMode === 'dark' ? 'ri-moon-line' : 'ri-sun-line'"></i>
          {{ themeMode === 'dark' ? '深色' : '浅色' }}
        </button>
        <span class="badge">海鸥派 NPU 在线</span>
      </div>
    </header>

    <main class="app-body">
      
      <section v-if="activeTab === 'home'" class="page-content fade-in">
        <div class="weather-card capsule-card">
          <div class="weather-info">
            <i :class="weatherIcon" class="weather-icon"></i>
            <div>
              <div class="weather-title-row">
                <h3>{{ weather.temperature }}°C / {{ weather.condition }}</h3>
                <span class="city-chip"><i class="ri-map-pin-line"></i>{{ weather.city }}</span>
              </div>
              <p>早上好, Williams. 今天是 {{ currentYear }}年{{ currentMonth }}月{{ currentDay }}日，{{ weatherAdvice }}。</p>
            </div>
          </div>
        </div>

        <div class="ai-recommendation capsule-card">
          <div class="recommend-content">
            <span class="tag-ai">AI 穿搭决策 · 天气参考</span>
            <h2>今日出行最佳推荐</h2>
            <div class="outfit-preview">
              <div class="cloth-item-mini" v-for="cloth in todayRecommendation.items" :key="cloth.id">
                <i :class="cloth.icon"></i> {{ cloth.name }}
              </div>
            </div>
            <p class="recommend-reason">{{ todayRecommendation.reason }}</p>
            <div class="recommend-footer">
              <span>搭配评分：{{ todayRecommendation.score }}分 · {{ weather.city }}</span>
              <button class="action-btn-sm" @click="saveCurrentToCalendar()">保存到今天日历</button>
            </div>
          </div>
        </div>

        <div class="quick-cards-grid">
          <div class="quick-card" @click="activeTab = 'wardrobe'">
            <i class="ri-door-closed-line"></i>
            <h4>我的衣柜</h4>
            <p>{{ mockClothes.length }}件单品 · {{ wardrobeSourceLabel }}</p>
          </div>
          <div class="quick-card" @click="activeTab = 'calendar'">
            <i class="ri-calendar-check-line"></i>
            <h4>穿搭日历</h4>
            <p>{{ recentLogCount }} 条记录</p>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'wardrobe'" class="page-content fade-in">
        <div class="section-title-row">
          <div>
            <h2>我的衣柜</h2>
            <p>{{ selectedCategory }} · 找到 {{ filteredClothes.length }} 件 · {{ wardrobeSourceLabel }}</p>
          </div>
          <button class="mini-outline-btn" @click="refreshWardrobeFromCloud">
            {{ wardrobeLoading ? '同步中' : '刷新云端' }}
          </button>
        </div>

        <div v-if="wardrobeLoadError" class="cloud-warning">
          <i class="ri-wifi-off-line"></i>
          云端衣柜加载失败，当前显示本地演示数据：{{ wardrobeLoadError }}
        </div>

        <div class="ai-camera-entry capsule-card" @click="triggerCameraMock">
          <div class="camera-content">
            <div class="camera-icon-wrap animate-pulse-slow">
              <i class="ri-camera-lens-line"></i>
            </div>
            <div class="camera-text">
              <h3>AI 大模型拍照入库</h3>
              <p>摄像头拍摄单品 ➔ 本地 NPU 大模型智能识别 ➔ 自动分类放进衣柜</p>
            </div>
            <i class="ri-arrow-right-s-line arrow-right"></i>
          </div>
        </div>

        <div class="search-bar-wrap">
          <input 
            type="text" 
            v-model="searchQuery" 
            placeholder="搜索颜色 / 季节 / 领型 / 夹克..." 
          />
          <i class="ri-search-2-line" :style="{ color: searchQuery ? '#000' : '#999' }"></i>
        </div>

        <div class="filter-tabs">
          <span 
            v-for="cat in wardrobeCategories" 
            :key="cat"
            class="f-tag"
            :class="{ active: selectedCategory === cat }"
            @click="selectedCategory = cat"
          >
            {{ cat }}
          </span>
        </div>

        <div v-if="filteredClothes.length === 0" class="empty-state">
          <i class="ri-search-eye-line"></i>
          <h4>没有找到匹配单品</h4>
          <p>可以试试输入“灰色”“春秋”“衬衫”或切换分类。</p>
        </div>
        
        <div v-else class="clothes-grid">
          <div 
            class="cloth-card" 
            :class="{ 'background-selected': highlightedClothId === item.id }"
            :data-cloth-id="item.id"
            v-for="item in filteredClothes" 
            :key="item.id"
            @click="openClothDetail(item)"
          >
            <div class="cloth-img-wrapper">
              <img :src="item.img" alt="衣服照片" />
            </div>
            
            <div class="cloth-info">
              <h4>{{ item.name }}</h4>
              <div class="cloth-meta-row">
                <span class="cloth-tag-season">{{ item.season }} · {{ item.type }}</span>
                <span class="cloth-count">{{ item.count }} 次</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'match'" class="page-content fade-in">
        <div class="match-hero capsule-card">
          <span class="tag-ai">搭配工作台</span>
          <h2>{{ currentScene }}穿搭推荐</h2>
          <p>{{ weather.city }}当前 {{ weather.temperature }}°C / {{ weather.condition }}，系统会使用{{ wardrobeSourceLabel }}做天气适配。</p>
        </div>

        <div class="match-input-box">
          <div class="match-toolbar">
            <div>
              <h4>选择场景</h4>
              <p>也可以直接随机生成一套适合今天的穿搭。</p>
            </div>
            <button class="random-btn" type="button" @click="randomizeOutfit">
              <i class="ri-shuffle-line"></i> 随机一套
            </button>
          </div>
          <div class="scene-tags">
            <span
              class="scene-tag"
              :class="{ active: currentScene === scene }"
              v-for="scene in scenes"
              :key="scene"
              @click="currentScene = scene"
            >
              {{ scene }}
            </span>
          </div>
        </div>

        <div class="ai-match-result-card fade-in" :key="`${effectiveScene}-${randomSeed}`">
          <div class="match-card-header">
            <span class="ai-badge-neon">{{ matchRecommendation.badge }}</span>
            <div class="match-score">匹配度 <strong>{{ matchRecommendation.score }}</strong> 分</div>
          </div>
          
          <h3 class="match-title">{{ matchRecommendation.title }}</h3>
          <p class="match-desc">{{ matchRecommendation.desc }}</p>
          
          <div class="match-items-row">
            <div class="match-item-mini" v-for="cloth in matchRecommendation.items" :key="cloth.id">
              <div class="mini-img-wrap">
                <img :src="cloth.img" alt="衣服" />
              </div>
              <div class="mini-meta">
                <span>{{ cloth.name }}</span>
                <small class="badge-type">{{ cloth.type }} · {{ cloth.season }}</small>
              </div>
            </div>
          </div>

          <div class="match-reason-list">
            <div v-for="reason in matchRecommendation.reasons" :key="reason">
              <i class="ri-check-line"></i>{{ reason }}
            </div>
          </div>

          <button class="action-btn-full" style="border-radius: 8px;" @click="handleApplyOutfit()">
            <i class="ri-check-double-line"></i> 采纳这套并同步到穿搭日历
          </button>
        </div>
      </section>

      <section v-if="activeTab === 'calendar'" class="page-content fade-in">
        <div class="calendar-header-card">
          <div class="calendar-month-title">
            <i class="ri-calendar-event-line"></i>
            <h3>近十天穿搭记录</h3>
          </div>
          <p class="calendar-subtext">按自然周分组展示最近 10 天。未来日期不会显示，没有真实保存记录时显示“无”。</p>
        </div>

        <div class="week-calendar-list">
          <div class="week-card" v-for="week in recentWeekGroups" :key="week.key">
            <div class="week-title">{{ week.label }}</div>
            <div class="week-days-row">
              <button
                v-for="day in week.days"
                :key="day.key"
                class="week-day-cell"
                :class="{ selected: selectedCalendarDate === day.key, today: day.isToday, 'has-data': calendarHistory[day.key] }"
                type="button"
                @click="selectDate(day.key)"
              >
                <span>{{ day.weekday }}</span>
                <strong>{{ day.month }}/{{ day.day }}</strong>
                <em>{{ calendarHistory[day.key] ? '有记录' : '无' }}</em>
              </button>
            </div>
          </div>
        </div>

        <div class="history-detail-panel fade-in" :key="selectedCalendarDate">
          <h4>{{ selectedCalendarLabel }} 穿搭日志</h4>
          
          <div v-if="selectedCalendarLog" class="history-card-active">
            <div class="history-badge-row">
              <span class="scene-badge">{{ selectedCalendarLog.scene }}场景</span>
              <span class="score-badge">评分: {{ selectedCalendarLog.score }}分</span>
            </div>
            <h5>{{ selectedCalendarLog.title }}</h5>
            <p class="calendar-note">以下为这一天真实保存过的穿搭单品。</p>
            
            <div class="history-items-list">
              <div 
                class="history-item-tag" 
                v-for="(itemName, idx) in selectedCalendarLog.items" 
                :key="idx"
              >
                {{ itemName }}
              </div>
            </div>
          </div>
          <div v-else class="no-data-placeholder">
            <strong>无</strong>
            <p>这一天没有真实保存的穿搭日志。</p>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'me'" class="page-content fade-in">
        <div class="common-card-rounded" style="display: flex; flex-direction: row; gap: 15px; align-items: center; margin-top: 4px;">
          <div class="avatar-circle" style="width: 60px; height: 60px; font-size: 32px;">
            <i class="ri-user-3-line"></i>
          </div>
          <div style="text-align: left; flex: 1;">
            <h3 style="margin: 0; font-size: 20px; font-weight: 900;">Williams</h3>
            <p style="margin: 4px 0 0 0; color: #666; font-size: 12px;">智能衣橱高级用户</p>
          </div>
          <i class="ri-settings-3-line" style="font-size: 22px; color: #999; cursor: pointer;"></i>
        </div>

        <div class="quick-cards-grid" style="grid-template-columns: 1fr 1fr;">
          <div class="quick-card">
            <h4 style="font-size: 20px;">{{ mockClothes.length }}</h4>
            <p style="margin-top: 4px;">数字单品</p>
          </div>
          <div class="quick-card">
            <h4 style="font-size: 20px;">{{ recentLogCount }}</h4>
            <p style="margin-top: 4px;">近十天日志</p>
          </div>
        </div>

        <div class="common-card-rounded" style="padding: 4px 20px;">
          <div class="list-item">
            <div class="list-item-left"><i class="ri-contrast-2-line"></i> <span>显示模式</span></div>
            <div class="theme-segment">
              <button :class="{ active: themeMode === 'light' }" type="button" @click="setTheme('light')">浅色</button>
              <button :class="{ active: themeMode === 'dark' }" type="button" @click="setTheme('dark')">深色</button>
            </div>
          </div>
          <div class="list-item">
            <div class="list-item-left"><i class="ri-macbook-line"></i> <span>硬件衣柜绑定</span></div>
            <div class="list-item-right"><span style="color: #00FF66; font-size: 12px; margin-right: 4px; font-weight: bold;">已连接海鸥派</span><i class="ri-arrow-right-s-line"></i></div>
          </div>
          <div class="list-item">
            <div class="list-item-left"><i class="ri-brain-line"></i> <span>NPU 大模型配置</span></div>
            <div class="list-item-right"><span style="color: #999; font-size: 12px; margin-right: 4px;">本地边缘计算</span><i class="ri-arrow-right-s-line"></i></div>
          </div>
          <div class="list-item">
            <div class="list-item-left"><i class="ri-customer-service-2-line"></i> <span>帮助与反馈</span></div>
            <div class="list-item-right"><i class="ri-arrow-right-s-line"></i></div>
          </div>
          <div class="list-item" style="border-bottom: none;">
            <div class="list-item-left"><i class="ri-information-line"></i> <span>关于 ClothesAI</span></div>
            <div class="list-item-right"><span style="color: #999; font-size: 12px; margin-right: 4px;">v2.0 Beta</span><i class="ri-arrow-right-s-line"></i></div>
          </div>
        </div>
      </section>

    </main>

    <Transition name="cloth-modal">
      <div v-if="selectedCloth" class="cloth-detail-overlay" @click="closeClothDetail" @wheel.prevent @touchmove.prevent>
        <div ref="clothDetailModal" class="cloth-detail-modal" @click.stop @wheel.stop @touchmove.stop>
          <button class="modal-close-btn" type="button" @click="closeClothDetail">
            <i class="ri-close-line"></i>
          </button>
          <div class="cloth-detail-image">
            <img :src="selectedCloth.img" :alt="selectedCloth.name" />
          </div>
          <div class="cloth-detail-content">
            <span class="cloth-detail-type">{{ selectedCloth.type }}</span>
            <h3>{{ selectedCloth.name }}</h3>
            <div class="cloth-detail-meta">
              <span><i class="ri-palette-line"></i>{{ selectedCloth.color }}</span>
              <span><i class="ri-sun-line"></i>{{ selectedCloth.season }}</span>
              <span><i class="ri-repeat-line"></i>{{ selectedCloth.count }} 次穿着</span>
            </div>

            <div class="pairing-section">
              <div class="pairing-title-row">
                <h4>可搭配单品</h4>
                <span>{{ selectedClothPairings.length }} 件推荐</span>
              </div>
              <div class="pairing-grid">
                <button
                  v-for="item in selectedClothPairings"
                  :key="item.id"
                  class="pairing-card"
                  type="button"
                  @click="selectPairingCloth(item)"
                >
                  <img :src="item.img" :alt="item.name" />
                  <span>{{ item.name }}</span>
                  <small>{{ item.type }} · {{ item.color }}</small>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="app-dialog">
      <div v-if="appDialog.visible" class="app-dialog-overlay" @click.self="closeAppDialog(false)">
        <div class="app-dialog-card" role="dialog" aria-modal="true">
          <div class="app-dialog-icon" :class="`dialog-${appDialog.variant}`">
            <i :class="appDialog.icon"></i>
          </div>
          <div class="app-dialog-content">
            <p class="app-dialog-kicker">{{ appDialog.kicker }}</p>
            <h3>{{ appDialog.title }}</h3>
            <p>{{ appDialog.message }}</p>
          </div>
          <div class="app-dialog-actions" :class="{ 'has-cancel': appDialog.cancelText }">
            <button v-if="appDialog.cancelText" class="dialog-btn dialog-btn-ghost" type="button" @click="closeAppDialog(false)">
              {{ appDialog.cancelText }}
            </button>
            <button class="dialog-btn dialog-btn-primary" type="button" @click="closeAppDialog(true)">
              {{ appDialog.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <nav class="app-nav-bar">
      <div class="nav-item" :class="{ active: activeTab === 'home' }" @click="activeTab = 'home'">
        <div class="icon-wrapper">
          <i class="ri-home-5-line"></i>
        </div>
        <span>首页</span>
      </div>
      
      <div class="nav-item" :class="{ active: activeTab === 'wardrobe' }" @click="activeTab = 'wardrobe'">
        <div class="icon-wrapper">
          <i class="ri-box-3-line"></i>
        </div>
        <span>我的衣柜</span>
      </div>
      
      <div class="nav-item" :class="{ active: activeTab === 'match' }" @click="activeTab = 'match'">
        <div class="icon-wrapper">
          <i class="ri-magic-line"></i>
        </div>
        <span>搭配</span>
      </div>
      
      <div class="nav-item" :class="{ active: activeTab === 'calendar' }" @click="activeTab = 'calendar'">
        <div class="icon-wrapper">
          <i class="ri-calendar-2-line"></i>
        </div>
        <span>日历</span>
      </div>
      
      <div class="nav-item" :class="{ active: activeTab === 'me' }" @click="activeTab = 'me'">
        <div class="icon-wrapper">
          <i class="ri-user-line"></i>
        </div>
        <span>我</span>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import 'remixicon/fonts/remixicon.css'

function toDateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(date, offset) {
  const next = new Date(date)
  next.setDate(next.getDate() + offset)
  return next
}

function startOfWeek(date) {
  const start = new Date(date)
  const day = start.getDay()
  const offset = day === 0 ? -6 : 1 - day
  start.setDate(start.getDate() + offset)
  return start
}

function formatDateLabel(key) {
  const [year, month, day] = key.split('-')
  return `${Number(month)}月${Number(day)}日`
}

const todayObj = new Date()
const currentYear = ref(todayObj.getFullYear())   
const currentMonth = ref(todayObj.getMonth() + 1) 
const currentDay = ref(todayObj.getDate())        

const activeTab = ref('home')
const selectedCategory = ref('全部')
const searchQuery = ref('')
const selectedCloth = ref(null)
const clothDetailModal = ref(null)
const highlightedClothId = ref(0)
const wardrobeSource = ref('demo')
const wardrobeLoading = ref(false)
const wardrobeLoadError = ref('')
const wardrobeLastLoadedAt = ref('')
const selectedCalendarDate = ref(toDateKey(todayObj))
const currentScene = ref('上班')
const scenes = ['随机', '上班', '约会', '旅行', '运动', '休闲']
const randomScene = ref('休闲')
const randomSeed = ref(0)
const themeMode = ref(localStorage.getItem('clothesai-theme') || 'light')
const wardrobeCategories = ['全部', '衬衫/T恤', '卫衣/针织', '夹克/皮衣', '日常裤装', '鞋履']
let backgroundScrollTimer = 0
const wardrobeApiBase = (import.meta.env.VITE_WARDROBE_API_BASE || '').replace(/\/$/, '')
const wardrobeDeviceId = String(import.meta.env.VITE_WARDROBE_DEVICE_ID || 'ss928_001').trim()
const appDialog = ref({
  visible: false,
  variant: 'success',
  icon: 'ri-check-line',
  kicker: 'ClothesAI',
  title: '',
  message: '',
  confirmText: '知道了',
  cancelText: '',
  resolve: null,
})

const weather = ref({
  city: '定位中',
  temperature: 24,
  condition: '晴',
  code: 0,
  loading: true,
  source: 'loading',
})

const themeClass = computed(() => themeMode.value === 'dark' ? 'theme-dark' : 'theme-light')

const weatherIcon = computed(() => {
  if (weather.value.condition.includes('雨')) return 'ri-rainy-line'
  if (weather.value.condition.includes('雪')) return 'ri-snowy-line'
  if (weather.value.condition.includes('阴') || weather.value.condition.includes('云')) return 'ri-sun-cloudy-line'
  return 'ri-sun-line'
})

const weatherAdvice = computed(() => {
  const temp = weather.value.temperature
  if (temp <= 8) return '气温偏低，建议选择保暖外套和长裤'
  if (temp <= 18) return '早晚有凉意，适合薄外套加长裤'
  if (temp >= 30) return '天气偏热，优先选择短袖和透气轻薄单品'
  return '天气舒适，适合短袖衬衫加薄外套'
})

const effectiveScene = computed(() => currentScene.value === '随机' ? randomScene.value : currentScene.value)
const todayRecommendation = computed(() => buildRecommendation('上班'))
const matchRecommendation = computed(() => buildRecommendation(effectiveScene.value))
const wardrobeSourceLabel = computed(() => {
  if (wardrobeLoading.value) return '云端同步中'
  if (wardrobeSource.value === 'cloud') return `云端真实衣柜${wardrobeLastLoadedAt.value ? ` ${wardrobeLastLoadedAt.value}` : ''}`
  return '本地演示衣柜'
})

const syncDocumentTheme = (mode) => {
  const isDark = mode === 'dark'
  document.documentElement.classList.toggle('app-dark-shell', isDark)
  document.body.classList.toggle('app-dark-shell', isDark)
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
}

const dialogIconMap = {
  success: 'ri-check-line',
  info: 'ri-information-line',
  warning: 'ri-loop-right-line',
}

const openAppDialog = ({
  variant = 'success',
  kicker = 'ClothesAI',
  title,
  message,
  confirmText = '知道了',
  cancelText = '',
}) => new Promise((resolve) => {
  appDialog.value = {
    visible: true,
    variant,
    icon: dialogIconMap[variant] || dialogIconMap.info,
    kicker,
    title,
    message,
    confirmText,
    cancelText,
    resolve,
  }
})

const closeAppDialog = (confirmed) => {
  const resolver = appDialog.value.resolve
  appDialog.value.visible = false
  appDialog.value.resolve = null
  resolver?.(confirmed)
}

const showNotice = (title, message, variant = 'success') => openAppDialog({
  variant,
  title,
  message,
  confirmText: '好的',
})

const showConfirm = (title, message, confirmText = '覆盖', cancelText = '保留原记录') => openAppDialog({
  variant: 'warning',
  title,
  message,
  confirmText,
  cancelText,
})

const weatherCodeName = (code) => {
  if ([0, 1].includes(code)) return '晴'
  if ([2, 3].includes(code)) return '多云'
  if ([45, 48].includes(code)) return '雾'
  if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return '雨'
  if ([71, 73, 75, 85, 86].includes(code)) return '雪'
  if ([95, 96, 99].includes(code)) return '雷阵雨'
  return '晴'
}

const defaultLocation = {
  city: '成都',
  latitude: 30.67,
  longitude: 104.06,
}

const loadLocationByIp = async () => {
  const locationResponse = await fetch('https://ipapi.co/json/')
  if (!locationResponse.ok) throw new Error(`location failed: ${locationResponse.status}`)
  const location = await locationResponse.json()
  return {
    city: location.city || location.region || defaultLocation.city,
    latitude: Number(location.latitude || defaultLocation.latitude),
    longitude: Number(location.longitude || defaultLocation.longitude),
  }
}

const loadWeatherByIp = async () => {
  let location = defaultLocation
  let source = 'default-city'

  try {
    location = await loadLocationByIp()
    source = 'ip'
  } catch (error) {
    console.warn('IP 定位失败，使用默认城市查询天气', error)
  }

  try {
    const weatherResponse = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${location.latitude}&longitude=${location.longitude}&current=temperature_2m,weather_code&timezone=auto`
    )
    if (!weatherResponse.ok) throw new Error('weather failed')
    const payload = await weatherResponse.json()
    const current = payload.current || {}
    weather.value = {
      city: location.city,
      temperature: Math.round(Number(current.temperature_2m ?? 24)),
      condition: weatherCodeName(Number(current.weather_code ?? 0)),
      code: Number(current.weather_code ?? 0),
      loading: false,
      source,
    }
  } catch (error) {
    console.warn('天气接口失败，使用本地默认天气', error)
    weather.value = {
      city: location.city,
      temperature: 24,
      condition: '晴',
      code: 0,
      loading: false,
      source: 'fallback',
    }
  }
}

const calendarHistory = ref(JSON.parse(localStorage.getItem('clothesai-calendar') || '{}'))

const recentCalendarDays = computed(() => {
  return Array.from({ length: 10 }, (_, index) => {
    const date = addDays(todayObj, -index)
    const key = toDateKey(date)
    return {
      key,
      date,
      day: date.getDate(),
      month: date.getMonth() + 1,
      weekday: ['日', '一', '二', '三', '四', '五', '六'][date.getDay()],
      isToday: key === toDateKey(todayObj),
    }
  }).reverse()
})

const recentWeekGroups = computed(() => {
  const groups = []
  for (const day of recentCalendarDays.value) {
    const weekStart = startOfWeek(day.date)
    const weekEnd = addDays(weekStart, 6)
    const key = toDateKey(weekStart)
    let group = groups.find(item => item.key === key)
    if (!group) {
      group = {
        key,
        label: `${formatDateLabel(toDateKey(weekStart))} - ${formatDateLabel(toDateKey(weekEnd))}`,
        days: [],
      }
      groups.push(group)
    }
    group.days.push(day)
  }
  return groups
})

const selectedCalendarLog = computed(() => calendarHistory.value[selectedCalendarDate.value])
const selectedCalendarLabel = computed(() => formatDateLabel(selectedCalendarDate.value))
const recentLogCount = computed(() => recentCalendarDays.value.filter(day => calendarHistory.value[day.key]).length)

const persistCalendar = () => {
  localStorage.setItem('clothesai-calendar', JSON.stringify(calendarHistory.value))
}

const selectDate = (key) => {
  selectedCalendarDate.value = key
}

const createCalendarEntry = (scene, data) => ({
  scene,
  title: data.title,
  score: data.score,
  items: data.items.map(i => i.name),
  savedAt: new Date().toISOString(),
})

const hasSameOutfit = (current, next) => {
  if (!current) return false
  return current.scene === next.scene
    && current.title === next.title
    && current.score === next.score
    && JSON.stringify(current.items || []) === JSON.stringify(next.items || [])
}

const saveCalendarEntry = async (key, scene, data) => {
  const nextEntry = createCalendarEntry(scene, data)
  const existingEntry = calendarHistory.value[key]
  const label = formatDateLabel(key)

  if (hasSameOutfit(existingEntry, nextEntry)) {
    await showNotice('已经保存过了', `${label} 已经有这套穿搭，无需重复保存。`, 'info')
    return false
  }

  if (existingEntry) {
    const shouldOverwrite = await showConfirm(
      '覆盖原有穿搭？',
      `${label} 已有穿搭日志，新的穿搭和原记录不一样。确认后会用这套新搭配替换原记录。`,
      '覆盖更新',
      '先不覆盖'
    )
    if (!shouldOverwrite) return false
  }

  calendarHistory.value[key] = {
    ...nextEntry,
    savedAt: new Date().toISOString(),
  }
  persistCalendar()
  return true
}

const handleApplyOutfit = async () => {
  const scene = effectiveScene.value
  const data = buildRecommendation(scene)
  const didSave = await saveCalendarEntry(selectedCalendarDate.value, scene, data)
  if (!didSave) return
  await showNotice('同步成功', `已将“${scene}”穿搭记录到 ${selectedCalendarLabel.value} 的穿搭日历中。`)
  activeTab.value = 'calendar'
}

const saveCurrentToCalendar = async () => {
  const data = todayRecommendation.value
  const todayKey = toDateKey(todayObj)
  selectedCalendarDate.value = todayKey
  const didSave = await saveCalendarEntry(todayKey, '上班', data)
  if (!didSave) return
  await showNotice('保存成功', `首页推荐已同步至今日 (${formatDateLabel(todayKey)}) 穿搭日历。`)
}

const setTheme = (mode) => {
  themeMode.value = mode
  localStorage.setItem('clothesai-theme', mode)
  syncDocumentTheme(mode)
}

const toggleTheme = () => {
  setTheme(themeMode.value === 'dark' ? 'light' : 'dark')
}

const randomizeOutfit = () => {
  const pool = scenes.filter(scene => scene !== '随机')
  randomScene.value = pool[Math.floor(Math.random() * pool.length)] || '休闲'
  randomSeed.value += 1
  currentScene.value = '随机'
}

const mockClothes = ref([
  { id: 1, name: '科技青工装衬衫 (翻领)', type: '衬衫/T恤', season: '春秋', color: '青色蓝', count: 12, img: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=300&q=80' },
  { id: 4, name: '复古白百搭纯T (圆领)', type: '衬衫/T恤', season: '夏季', color: '白色', count: 24, img: 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=300&q=80' },
  { id: 7, name: '古巴领重装墨绿短衬', type: '衬衫/T恤', season: '夏季', color: '绿色', count: 6, img: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=300&q=80' },
  { id: 6, name: '燕麦色开襟针织衫 (V领)', type: '卫衣/针织', season: '春秋', color: '燕麦色', count: 3, img: 'https://images.unsplash.com/photo-1614975058789-41316d0e2e9c?auto=format&fit=crop&w=300&q=80' },
  { id: 8, name: '连帽重磅落肩落叶黄卫衣', type: '卫衣/针织', season: '冬季', color: '黄色', count: 9, img: 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=300&q=80' },
  { id: 9, name: '微高领华夫格水泥灰卫衣', type: '卫衣/针织', season: '春秋', color: '灰色', count: 11, img: 'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?auto=format&fit=crop&w=300&q=80' },
  { id: 3, name: '深空蓝连帽防风外套', type: '夹克/皮衣', season: '冬季', color: '蓝色', count: 15, img: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=300&q=80' },
  { id: 10, name: '石墨黑重机复古机车皮夹克', type: '夹克/皮衣', season: '冬季', color: '黑色', count: 4, img: 'https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?auto=format&fit=crop&w=300&q=80' },
  { id: 11, name: '经典水洗蓝单排扣牛仔夹克', type: '夹克/皮衣', season: '春秋', color: '蓝色', count: 14, img: 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?auto=format&fit=crop&w=300&q=80' },
  { id: 12, name: '山系野外MA-1军事黑飞行夹克', type: '夹克/皮衣', season: '冬季', color: '黑色', count: 7, img: 'https://images.unsplash.com/photo-1548883354-7622d03aca27?auto=format&fit=crop&w=300&q=80' },
  { id: 2, name: '莫兰迪灰微锥直休闲裤', type: '日常裤装', season: '四季', color: '灰色', count: 8, img: 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=300&q=80' },
  { id: 5, name: '暗黑系多口袋修身工装裤', type: '日常裤装', season: '春秋', color: '黑色', count: 5, img: 'https://images.unsplash.com/photo-1517423568366-8b83523034fd?auto=format&fit=crop&w=300&q=80' },
  { id: 13, name: '经典原色宽松直筒大廓形牛仔裤', type: '日常裤装', season: '四季', color: '蓝色', count: 19, img: 'https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=300&q=80' },
  { id: 14, name: '机能风抽绳束脚立体卡其裤', type: '日常裤装', season: '春秋', color: '卡其色', count: 10, img: 'https://images.unsplash.com/photo-1473968512647-3e447244af8f?auto=format&fit=crop&w=300&q=80' },
  { id: 15, name: '夏季高弹轻量透气速干运动短裤', type: '日常裤装', season: '夏季', color: '黑色', count: 22, img: 'https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=300&q=80' },
  { id: 16, name: '白色低帮缓震运动鞋', type: '鞋履', season: '四季', color: '白色', count: 16, img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=300&q=80' },
  { id: 17, name: '黑色通勤皮质短靴', type: '鞋履', season: '秋冬', color: '黑色', count: 7, img: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=300&q=80' },
  { id: 18, name: '灰白轻量跑步鞋', type: '鞋履', season: '春夏', color: '灰色', count: 11, img: 'https://images.unsplash.com/photo-1460353581641-37baddab0fa2?auto=format&fit=crop&w=300&q=80' }
])

const fallbackClothImage = 'https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=500&q=80'

const cloudTypeMap = {
  top: '衬衫/T恤',
  shirt: '衬衫/T恤',
  tshirt: '衬衫/T恤',
  bottom: '日常裤装',
  pants: '日常裤装',
  outer: '夹克/皮衣',
  jacket: '夹克/皮衣',
  coat: '夹克/皮衣',
  shoes: '鞋履',
  shoe: '鞋履',
}

const cloudSeasonMap = {
  spring_autumn: '春秋',
  summer_light: '夏季',
  summer_hot: '夏季',
  winter: '冬季',
  all: '四季',
}

const normalizeCloudType = (type) => {
  const text = String(type || '').trim()
  return cloudTypeMap[text.toLowerCase()] || text || '衬衫/T恤'
}

const normalizeCloudSeason = (season) => {
  const tags = String(season || '').replace(/，/g, ',').replace(/、/g, ',').split(',')
    .map(item => item.trim())
    .filter(Boolean)
  if (!tags.length) return '四季'
  const labels = [...new Set(tags.map(tag => cloudSeasonMap[tag.toLowerCase()] || tag))]
  if (labels.includes('四季') || labels.length >= 3) return '四季'
  return labels.join('、')
}

const normalizeCloudCloth = (item) => ({
  id: item.id,
  name: item.name || '未命名衣物',
  type: normalizeCloudType(item.type),
  season: normalizeCloudSeason(item.season),
  color: item.color || '未知',
  count: Number(item.count || 0),
  img: item.img || item.imageUrl || fallbackClothImage,
  material: item.material || '',
  location: item.location || '',
  confidence: item.confidence ?? null,
  spectralSignature: item.spectralSignature || {},
  lastSeenAt: item.lastSeenAt || item.updatedAt || '',
})

const belongsToCurrentWardrobe = (item) => {
  if (!item || item.id === 'cloth_demo_001') return false
  if (!wardrobeDeviceId) return true
  const source = String(item.source || item.deviceId || '')
  const id = String(item.id || '')
  return source === wardrobeDeviceId || id.startsWith(`${wardrobeDeviceId}_`)
}

const loadWardrobeFromCloud = async () => {
  if (!wardrobeApiBase) return
  wardrobeLoading.value = true

  try {
    const response = await fetch(`${wardrobeApiBase}/api/wardrobe/items?t=${Date.now()}`, {
      cache: 'no-store',
    })
    if (!response.ok) throw new Error(`wardrobe api failed: ${response.status}`)
    const payload = await response.json()
    const items = Array.isArray(payload) ? payload : payload.items
    if (!Array.isArray(items)) throw new Error('wardrobe api response missing items')
    mockClothes.value = items
      .filter(belongsToCurrentWardrobe)
      .map(normalizeCloudCloth)
    wardrobeSource.value = 'cloud'
    wardrobeLoadError.value = ''
    wardrobeLastLoadedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (error) {
    console.warn('云端真实衣柜加载失败，继续使用本地演示衣柜', error)
    wardrobeSource.value = 'demo'
    wardrobeLoadError.value = error.message || '云端衣柜加载失败'
  } finally {
    wardrobeLoading.value = false
  }
}

const refreshWardrobeFromCloud = async () => {
  await loadWardrobeFromCloud()
}

const filteredClothes = computed(() => {
  return mockClothes.value.filter(cloth => {
    const matchCategory = selectedCategory.value === '全部' || cloth.type === selectedCategory.value
    const query = searchQuery.value.trim().toLowerCase()
    const searchable = `${cloth.name} ${cloth.color} ${cloth.season} ${cloth.type}`.toLowerCase()
    return matchCategory && (!query || searchable.includes(query))
  })
})

const wardrobeTopTypes = ['衬衫/T恤', '卫衣/针织', '夹克/皮衣']
const neutralColors = ['白色', '黑色', '灰色', '燕麦色', '卡其色']
const colorMatches = {
  白色: ['黑色', '灰色', '蓝色', '青色蓝', '绿色', '卡其色'],
  黑色: ['白色', '灰色', '蓝色', '卡其色', '黄色'],
  灰色: ['白色', '黑色', '蓝色', '青色蓝', '燕麦色'],
  蓝色: ['白色', '灰色', '黑色', '卡其色'],
  青色蓝: ['白色', '灰色', '黑色'],
  绿色: ['白色', '黑色', '卡其色'],
  黄色: ['黑色', '灰色', '蓝色'],
  燕麦色: ['白色', '灰色', '蓝色', '黑色'],
  卡其色: ['白色', '黑色', '绿色', '蓝色'],
}

const getPairingTypes = (cloth) => {
  if (!cloth) return []
  if (wardrobeTopTypes.includes(cloth.type)) return ['日常裤装', '鞋履']
  if (cloth.type === '日常裤装') return [...wardrobeTopTypes, '鞋履']
  if (cloth.type === '鞋履') return [...wardrobeTopTypes, '日常裤装']
  return ['日常裤装', '鞋履']
}

const compatibilityScore = (base, candidate) => {
  const colorScore = base.color === candidate.color
    ? 2
    : colorMatches[base.color]?.includes(candidate.color)
      ? 6
      : neutralColors.includes(candidate.color)
        ? 4
        : 1
  const seasonScoreValue = base.season === candidate.season
    ? 4
    : base.season.includes('四季') || candidate.season.includes('四季')
      ? 3
      : base.season.includes('春秋') && candidate.season.includes('春夏')
        ? 2
        : 0

  return colorScore + seasonScoreValue + Math.min(3, Math.floor(candidate.count / 8))
}

const selectedClothPairings = computed(() => {
  if (!selectedCloth.value) return []
  const targetTypes = getPairingTypes(selectedCloth.value)
  return mockClothes.value
    .filter(item => item.id !== selectedCloth.value.id && targetTypes.includes(item.type))
    .map(item => ({ ...item, matchScore: compatibilityScore(selectedCloth.value, item) }))
    .sort((a, b) => b.matchScore - a.matchScore)
    .slice(0, 4)
})

const clearWardrobeFilters = () => {
  selectedCategory.value = '全部'
  searchQuery.value = ''
}

const openClothDetail = (cloth) => {
  selectedCloth.value = cloth
  nextTick(() => {
    clothDetailModal.value?.scrollTo({ top: 0, behavior: 'auto' })
  })
}

const animateLockedBackgroundTo = (targetScrollTop) => {
  window.clearTimeout(backgroundScrollTimer)
  document.body.classList.add('cloth-modal-moving')
  window.requestAnimationFrame(() => {
    document.body.dataset.clothScrollTop = String(targetScrollTop)
    document.body.style.setProperty('--cloth-scroll-lock-top', `-${targetScrollTop}px`)
  })
  backgroundScrollTimer = window.setTimeout(() => {
    document.body.classList.remove('cloth-modal-moving')
    backgroundScrollTimer = 0
  }, 460)
}

const scrollWardrobeToCloth = (cloth) => {
  activeTab.value = 'wardrobe'
  const isVisible = filteredClothes.value.some(item => item.id === cloth.id)
  if (!isVisible) {
    selectedCategory.value = '全部'
    searchQuery.value = ''
  }

  nextTick(() => {
    const card = document.querySelector(`[data-cloth-id="${cloth.id}"]`)
    if (!card) return
    const lockedScrollTop = Number(document.body.dataset.clothScrollTop || window.scrollY || 0)
    const targetScrollTop = Math.max(0, lockedScrollTop + card.getBoundingClientRect().top - (window.innerHeight - card.getBoundingClientRect().height) / 2)
    if (document.body.classList.contains('cloth-modal-open')) {
      animateLockedBackgroundTo(targetScrollTop)
    } else {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    highlightedClothId.value = cloth.id
    setTimeout(() => {
      if (highlightedClothId.value === cloth.id) highlightedClothId.value = 0
    }, 1800)
  })
}

const selectPairingCloth = (cloth) => {
  scrollWardrobeToCloth(cloth)
  selectedCloth.value = cloth
  nextTick(() => {
    clothDetailModal.value?.scrollTo({ top: 0, behavior: 'smooth' })
  })
}

const closeClothDetail = () => {
  selectedCloth.value = null
}

const lockPageScroll = () => {
  if (document.body.classList.contains('cloth-modal-open')) return
  const scrollTop = window.scrollY || document.documentElement.scrollTop || 0
  document.body.dataset.clothScrollTop = String(scrollTop)
  document.body.style.setProperty('--cloth-scroll-lock-top', `-${scrollTop}px`)
  document.body.classList.add('cloth-modal-open')
}

const unlockPageScroll = () => {
  if (!document.body.classList.contains('cloth-modal-open')) return
  const scrollTop = Number(document.body.dataset.clothScrollTop || 0)
  window.clearTimeout(backgroundScrollTimer)
  backgroundScrollTimer = 0
  document.body.classList.remove('cloth-modal-moving')
  document.body.classList.remove('cloth-modal-open')
  document.body.style.removeProperty('--cloth-scroll-lock-top')
  delete document.body.dataset.clothScrollTop
  window.scrollTo(0, scrollTop)
}

watch(selectedCloth, (cloth) => {
  if (cloth) {
    lockPageScroll()
  } else {
    unlockPageScroll()
  }
})

onBeforeUnmount(() => {
  unlockPageScroll()
})

const sceneProfiles = {
  上班: {
    title: '商务通勤：科技感精干风',
    desc: '优先选择干净利落的上衣和直筒裤，兼顾通勤正式感与舒适度。',
    topTypes: ['衬衫/T恤', '夹克/皮衣'],
    bottomTypes: ['日常裤装'],
    colors: ['青色蓝', '灰色', '蓝色', '黑色'],
    shoeColors: ['黑色', '白色', '灰色'],
    badge: 'NPU 边缘决策',
  },
  约会: {
    title: '都市休闲：温柔轻熟风',
    desc: '降低攻击性，选择柔和色彩和干净层次，整体更亲和。',
    topTypes: ['卫衣/针织', '衬衫/T恤'],
    bottomTypes: ['日常裤装'],
    colors: ['燕麦色', '白色', '灰色', '蓝色'],
    shoeColors: ['白色', '灰色'],
    badge: '氛围感搭配',
  },
  旅行: {
    title: '户外探索：山系机能风',
    desc: '优先考虑防风、耐脏和活动空间，适合较长时间外出。',
    topTypes: ['夹克/皮衣', '衬衫/T恤'],
    bottomTypes: ['日常裤装'],
    colors: ['蓝色', '黑色', '卡其色', '绿色'],
    shoeColors: ['黑色', '灰色'],
    badge: '出行策略',
  },
  运动: {
    title: '轻量高弹：运动机能风',
    desc: '降低闷热感，优先选择透气、速干、活动限制少的单品。',
    topTypes: ['衬衫/T恤', '卫衣/针织'],
    bottomTypes: ['日常裤装'],
    colors: ['白色', '黑色', '灰色'],
    shoeColors: ['白色', '灰色'],
    badge: '轻量优先',
  },
  休闲: {
    title: '周末松弛：舒适街头风',
    desc: '以舒适和好搭为主，适合日常散步、逛街和朋友聚会。',
    topTypes: ['卫衣/针织', '衬衫/T恤', '夹克/皮衣'],
    bottomTypes: ['日常裤装'],
    colors: ['白色', '灰色', '蓝色', '卡其色'],
    shoeColors: ['白色', '灰色', '黑色'],
    badge: '舒适优先',
  },
}

const seasonScore = (cloth) => {
  if (!cloth || !cloth.season) return 0
  const temp = weather.value.temperature
  if (temp >= 30) {
    return cloth.season.includes('夏') ? 8 : cloth.season.includes('四季') ? 4 : -3
  }
  if (temp <= 8) {
    return cloth.season.includes('冬') ? 8 : cloth.season.includes('四季') ? 3 : -2
  }
  if (temp <= 18) {
    return cloth.season.includes('春秋') || cloth.season.includes('冬') ? 6 : 2
  }
  return cloth.season.includes('春秋') || cloth.season.includes('夏') || cloth.season.includes('四季') ? 5 : 0
}

const pickCloth = (profile, role, usedIds = [], seed = 0) => {
  const preferredTypes = role === 'top' ? profile.topTypes : role === 'shoe' ? ['鞋履'] : profile.bottomTypes
  const preferredColors = role === 'shoe' ? (profile.shoeColors || profile.colors) : profile.colors
  const candidates = mockClothes.value
    .filter(item => preferredTypes.includes(item.type) && !usedIds.includes(item.id))
    .map((item, index) => {
      const colorScore = preferredColors.includes(item.color) ? 5 : 0
      const useScore = Math.min(4, Math.floor(item.count / 6))
      const randomScore = currentScene.value === '随机' ? ((seed * 7 + item.id * 3 + index) % 7) : 0
      return { item, score: seasonScore(item) + colorScore + useScore + randomScore }
    })
    .sort((a, b) => b.score - a.score)

  if (currentScene.value === '随机' && candidates.length) {
    return candidates[seed % Math.min(3, candidates.length)].item
  }
  return candidates[0]?.item || mockClothes.value.find(item => !usedIds.includes(item.id))
}

const iconForCloth = (cloth) => {
  if (cloth.type === '鞋履') return 'ri-footprint-line'
  if (cloth.type === '日常裤装') return 'ri-layout-bottom-line'
  if (cloth.type === '夹克/皮衣') return 'ri-shirt-line'
  if (cloth.type === '卫衣/针织') return 'ri-t-shirt-2-line'
  return 'ri-t-shirt-line'
}

const buildRecommendation = (scene) => {
  const profile = sceneProfiles[scene] || sceneProfiles.休闲
  const seed = currentScene.value === '随机' ? randomSeed.value : 0
  const top = pickCloth(profile, 'top', [], seed)
  const bottom = pickCloth(profile, 'bottom', top ? [top.id] : [], seed + 1)
  const shoes = pickCloth(profile, 'shoe', [top?.id, bottom?.id].filter(Boolean), seed + 2)
  const items = [top, bottom, shoes].filter(Boolean).map(item => ({ ...item, icon: iconForCloth(item) }))
  const score = Math.min(99, 88 + items.length * 3 + Math.max(0, seasonScore(items[0] || {}) - 2))
  const weatherText = `${weather.value.city}${weather.value.temperature}°C/${weather.value.condition}`

  return {
    ...profile,
    score,
    items,
    reason: `${weatherText}，${weatherAdvice.value}；已从 ${wardrobeSourceLabel.value} ${mockClothes.value.length} 件单品中匹配。`,
    reasons: [
      `天气参考：${weatherAdvice.value}`,
      `场景参考：${profile.desc}`,
      `鞋履补全：${shoes ? shoes.name : '暂无合适鞋履'}`,
      `衣物来源：${wardrobeSourceLabel.value} ${mockClothes.value.length} 件单品`,
    ],
  }
}

const triggerCameraMock = () => {
  showNotice('真实衣柜入库', '后续由 SS928 识别衣物并上传到云端接口，App 会自动同步云端真实衣柜。', 'info')
}

const handleAppVisible = () => {
  if (document.visibilityState === 'visible') {
    loadWardrobeFromCloud()
  }
}

onMounted(() => {
  syncDocumentTheme(themeMode.value)
  loadWeatherByIp()
  loadWardrobeFromCloud()
  document.addEventListener('visibilitychange', handleAppVisible)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleAppVisible)
})
</script>

<style>
/* ==========================================
   DEWU 潮流方圆并济高级皮肤
   ========================================== */
.clothes-app-dark {
  width: 100%;
  max-width: 100vw;
  min-height: 100vh;
  min-height: 100svh;
  min-height: 100dvh;
  margin: 0 auto;
  background: #F8F9FA;
  display: flex;
  flex-direction: column;
  padding-bottom: calc(84px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #000000;
  position: relative;
  overflow-x: hidden;
}
.app-body { width: 100%; min-width: 0; padding-top: calc(62px + env(safe-area-inset-top)); }
.app-header { background: #FFFFFF; padding: calc(14px + env(safe-area-inset-top)) 16px 14px; border-bottom: 1px solid #EEF0F2; display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; position: fixed; top: 0; left: 0; right: 0; z-index: 10000; box-shadow: 0 6px 16px rgba(0, 0, 0, 0.035); }
.brand { display: flex; align-items: center; gap: 8px; font-weight: 900; font-size: clamp(17px, 5vw, 22px); min-width: 0; }
.brand span { min-width: 0; white-space: nowrap; }
.brand small { font-weight: normal; font-size: 11px; color: #888; }
.header-status { display: flex; align-items: center; justify-content: flex-end; gap: 8px; min-width: 0; }
.theme-toggle { display: inline-flex; align-items: center; gap: 4px; border: 1px solid #E5E5E5; background: #fff; color: #000; padding: 5px 9px; font-size: 10px; font-weight: 900; border-radius: 20px; white-space: nowrap; }
.badge { font-size: 10px; background: #000; color: #fff; padding: 5px 10px; font-weight: bold; border-radius: 20px; white-space: nowrap; }

.page-content { width: 100%; max-width: 520px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; }
.cloud-warning { display: flex; align-items: flex-start; gap: 8px; text-align: left; background: #FFF7E6; color: #7A4A00; border: 1px solid #FFE1A6; border-radius: 8px; padding: 10px 12px; font-size: 12px; font-weight: 700; line-height: 1.5; }
.cloud-warning i { font-size: 16px; margin-top: 1px; }
.capsule-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 24px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.015); overflow: hidden; }

.ai-camera-entry { padding: 18px 20px; background: #000000 !important; color: #FFFFFF !important; cursor: pointer; transition: all 0.2s ease; }
.ai-camera-entry:hover { transform: translateY(-1px); background: #1a1a1a !important; }
.camera-content { display: flex; align-items: center; justify-content: space-between; gap: 14px; text-align: left; }
.camera-icon-wrap { width: 44px; height: 44px; background: rgba(255,255,255,0.15); border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 22px; color: #00FF66; }
.camera-text { flex: 1; }
.camera-text h3 { margin: 0 0 4px 0; font-size: 15px; font-weight: 900; letter-spacing: 0.5px; }
.camera-text p { margin: 0; font-size: 11px; color: #B3B3B3; line-height: 1.4; }
.arrow-right { font-size: 20px; color: #888; }

.weather-card { padding: 18px 20px; text-align: left; }
.weather-info { display: flex; align-items: center; gap: 15px; }
.weather-icon { font-size: clamp(30px, 10vw, 44px); flex: 0 0 auto; }
.weather-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.weather-info h3 { margin: 0; font-size: 18px; font-weight: 900; }
.weather-info p { margin: 4px 0 0 0; font-size: 12px; color: #666; line-height: 1.4; }
.city-chip { display: inline-flex; align-items: center; gap: 3px; background: #F1F3F5; color: #555; border-radius: 999px; padding: 3px 8px; font-size: 11px; font-weight: 800; }

.ai-recommendation { background: #000; color: #fff; padding: 22px 20px; text-align: left; }
.tag-ai { background: #fff; color: #000; font-size: 10px; font-weight: 900; padding: 3px 8px; border-radius: 10px; }
.ai-recommendation h2 { margin: 10px 0 14px 0; font-size: 19px; font-weight: 900; }
.outfit-preview { display: flex; gap: 10px; margin: 12px 0; flex-wrap: wrap; }
.cloth-item-mini { background: rgba(255,255,255,0.1); padding: 8px 12px; font-size: 12px; border-radius: 8px; min-width: 0; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recommend-reason { color: #D6D6D6; font-size: 12px; line-height: 1.55; margin: 8px 0 14px; }
.recommend-footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 11px; flex-wrap: wrap; }
.action-btn-sm { background: #fff; color: #000; border: none; padding: 6px 16px; font-weight: 900; cursor: pointer; border-radius: 20px; }

.quick-cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 12px; }
.quick-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 16px; padding: 14px 8px; display: flex; flex-direction: column; align-items: center; cursor: pointer; transition: all 0.2s; }
.quick-card:hover { border-color: #000; }
.quick-card i { font-size: 24px; color: #000; margin-bottom: 4px; }
.quick-card h4 { font-size: 13px; font-weight: 700; margin: 0 0 2px 0; }
.quick-card p { font-size: 10px; color: #999; margin: 0; }

.section-title-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; text-align: left; }
.section-title-row h2 { margin: 0; font-size: 22px; font-weight: 900; }
.section-title-row p { margin-top: 3px; color: #777; font-size: 12px; }
.mini-outline-btn { border: 1px solid #ddd; background: #fff; border-radius: 999px; padding: 7px 12px; color: #111; font-size: 12px; font-weight: 800; }
.search-bar-wrap { display: flex; align-items: center; padding: 12px 18px; gap: 10px; background: #FFF; border: 1px solid #D8DDE3; border-radius: 30px; }
.search-bar-wrap input { border: none; width: 100%; min-width: 0; outline: none; font-size: 15px; background: transparent; color: #000; caret-color: #000; -webkit-text-fill-color: #000; }
.search-bar-wrap input::placeholder { color: #999; -webkit-text-fill-color: #999; }

.filter-tabs { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; }
.filter-tabs::-webkit-scrollbar { display: none; }
.f-tag { padding: 6px 16px; background: #fff; border: 1px solid #e5e5e5; font-size: 12px; cursor: pointer; white-space: nowrap; border-radius: 20px; transition: all 0.2s; }
.f-tag.active { background: #000; color: #fff; border-color: #000; font-weight: bold; }

.empty-state { background: #fff; border: 1px dashed #D8DDE3; border-radius: 18px; padding: 28px 18px; color: #777; }
.empty-state i { font-size: 28px; color: #111; }
.empty-state h4 { margin: 8px 0 4px; color: #111; }
.empty-state p { font-size: 12px; }
.clothes-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; min-height: 200px; }
.cloth-card { background: #FFFFFF; border: 1px solid #EEF0F2; border-radius: 16px; overflow: hidden; display: flex; flex-direction: column; position: relative; }
.cloth-card:active { transform: scale(0.99); }
.cloth-card.background-selected { border-color: #000; box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.08), 0 10px 24px rgba(0, 0, 0, 0.12); }
.cloth-img-wrapper { aspect-ratio: 1 / 1; width: 100%; background: #F1F3F5; overflow: hidden; }
.cloth-img-wrapper img { width: 100%; height: 100%; object-fit: cover; }
.cloth-info { padding: 12px; text-align: left; }
.cloth-info h4 { font-size: 13px; font-weight: 700; margin: 0 0 6px 0; height: 36px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.cloth-meta-row { display: flex; justify-content: space-between; align-items: center; }
.cloth-tag-season { font-size: 10px; color: #666; background: #F1F3F5; padding: 2px 6px; border-radius: 4px; }
.cloth-count { font-size: 11px; font-weight: 700; }

.calendar-header-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 16px; padding: 16px; text-align: left; }
.calendar-month-title { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.calendar-month-title h3 { margin: 0; font-size: 16px; font-weight: 900; }
.calendar-subtext { margin: 0; font-size: 11px; color: #777; }
.calendar-grid-box { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 20px; padding: 14px; display: flex; flex-direction: column; align-items: stretch; min-width: 0; }
.weekday-row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); justify-content: center; text-align: center; font-size: 11px; font-weight: bold; color: #999; margin-bottom: 12px; width: 100%; }
.days-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); justify-content: center; row-gap: 10px; width: 100%; }
.day-cell { width: clamp(34px, 10vw, 42px) !important; height: clamp(34px, 10vw, 42px) !important; border-radius: 50% !important; display: flex !important; flex-direction: column; justify-content: center; align-items: center; position: relative; cursor: pointer; background: #FAFAFA; box-sizing: border-box; margin: 0 auto; border: 1px solid transparent; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.day-cell.empty { background: transparent !important; border: none !important; cursor: default; }
.day-num { font-size: 12px; font-weight: bold; color: #333; line-height: 1; transition: color 0.15s; }
.day-cell.has-data { background: #FFFFFF; border: 1px solid #000000; }
.day-cell.today { box-shadow: inset 0 0 0 2px #00FF66; }
.day-cell.selected { background: #000000 !important; border-color: #000000 !important; }
.day-cell.selected .day-num { color: #FFFFFF !important; }
.data-dot { position: absolute; bottom: 4px; width: 4px; height: 4px; background: #00FF66; border-radius: 50%; }
.day-cell.selected .data-dot { background: #00FF66; box-shadow: 0 0 6px #00FF66; }

.week-calendar-list { display: flex; flex-direction: column; gap: 12px; }
.week-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 18px; padding: 14px; text-align: left; }
.week-title { font-size: 12px; font-weight: 900; color: #555; margin-bottom: 10px; }
.week-days-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(58px, 1fr)); gap: 8px; }
.week-day-cell { border: 1px solid #EEF0F2; background: #F8F9FA; color: #111; border-radius: 12px; padding: 8px 4px; display: flex; flex-direction: column; align-items: center; gap: 3px; min-width: 0; cursor: pointer; transition: all 0.2s ease; }
.week-day-cell span { font-size: 10px; color: #777; }
.week-day-cell strong { font-size: 13px; line-height: 1; }
.week-day-cell em { font-style: normal; font-size: 9px; color: #999; }
.week-day-cell.today { box-shadow: inset 0 0 0 2px #00FF66; }
.week-day-cell.has-data { border-color: #000; background: #fff; }
.week-day-cell.selected { background: #000; color: #fff; border-color: #000; }
.week-day-cell.selected span,
.week-day-cell.selected em { color: rgba(255,255,255,0.78); }
.calendar-note { color: #666; font-size: 11px; line-height: 1.45; margin-bottom: 10px; }

.history-detail-panel { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 20px; padding: 16px; text-align: left; }
.history-detail-panel h4 { margin: 0 0 12px 0; font-size: 14px; font-weight: 900; }
.history-card-active { background: #F8F9FA; border: 1px solid #EEF0F2; border-radius: 12px; padding: 14px; }
.history-badge-row { display: flex; gap: 8px; margin-bottom: 8px; }
.scene-badge { font-size: 10px; background: #000; color: #fff; padding: 2px 6px; font-weight: bold; border-radius: 4px; }
.score-badge { font-size: 10px; background: #EEE; color: #333; padding: 2px 6px; font-weight: bold; border-radius: 4px; }
.history-card-active h5 { margin: 0 0 10px 0; font-size: 13px; font-weight: 800; }
.history-items-list { display: flex; flex-wrap: wrap; gap: 8px; }
.no-data-placeholder { text-align: center; padding: 20px; color: #999; font-size: 12px; }

.history-item-tag { font-size: 11px; background: #FFF; border: 1px solid #E5E5E5; padding: 6px 12px; border-radius: 8px; display: flex; align-items: center; gap: 6px; font-weight: bold; }

.match-hero { background: #000; color: #fff; text-align: left; padding: 22px 20px; }
.match-hero h2 { margin: 10px 0 8px; font-size: 22px; font-weight: 900; }
.match-hero p { color: #d0d0d0; font-size: 13px; line-height: 1.55; }
.match-input-box { padding: 18px; text-align: left; border: 1px solid #E5E5E5; background: #fff; border-radius: 18px; }
.match-input-box h4 { margin: 0 0 12px 0; font-size: 14px; font-weight: 900; }
.match-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.match-toolbar h4 { margin: 0 0 4px 0; }
.match-toolbar p { color: #777; font-size: 12px; line-height: 1.4; }
.random-btn { flex: 0 0 auto; border: none; background: #000; color: #fff; padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 900; white-space: nowrap; }
.scene-tags { display: flex; gap: 8px; margin-top: 14px; overflow-x: auto; padding-bottom: 2px; }
.scene-tags::-webkit-scrollbar { display: none; }
.scene-tag { padding: 6px 16px; font-size: 12px; font-weight: 700; background: #fff; border: 1px solid #E5E5E5; cursor: pointer; white-space: nowrap; border-radius: 20px; transition: all 0.2s; }
.scene-tag.active { background: #000; color: #fff; border-color: #000; }
.ai-match-result-card { border: 1px solid #E5E5E5; padding: 20px; background: #FFFFFF; border-radius: 20px; }
.match-card-header { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.ai-badge-neon { font-size: 10px; font-weight: 900; background: #000; color: #fff; padding: 3px 8px; border-radius: 4px; }
.match-score { font-size: 12px; color: #666; }
.match-score strong { font-size: 18px; color: #000; }
.match-title { margin: 16px 0 8px 0; font-size: 16px; font-weight: 900; text-align: left; }
.match-desc { font-size: 13px; color: #666; line-height: 1.5; margin: 0 0 16px 0; text-align: left; }
.match-items-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.match-item-mini { min-width: 0; border: 1px solid #EEF0F2; border-radius: 12px; overflow: hidden; }
.mini-img-wrap { height: 110px; background: #F1F3F5; }
.mini-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.mini-meta { padding: 8px; text-align: left; }
.mini-meta span { font-size: 12px; font-weight: 700; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.badge-type { color: #777; font-size: 10px; }
.match-reason-list { display: grid; gap: 8px; margin-top: 14px; text-align: left; }
.match-reason-list div { background: #F8F9FA; border: 1px solid #EEF0F2; border-radius: 10px; padding: 9px 10px; font-size: 12px; color: #555; line-height: 1.45; }
.match-reason-list i { color: #000; margin-right: 5px; font-weight: 900; }

.action-btn-full { width: 100%; background: #000; color: #fff; border: none; padding: 12px; font-weight: 900; font-size: 13px; cursor: pointer; margin-top: 16px; }
.common-card-rounded { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 16px; padding: 20px; text-align: left; }
.avatar-circle { width: 50px; height: 50px; background: #F1F3F5; border: 1px solid #E5E5E5; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 24px; }

/* 🌟 “我”页面的专属列表项样式 */
.list-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid #EEF0F2; cursor: pointer; transition: all 0.2s; }
.list-item:hover { opacity: 0.7; }
.list-item-left { display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; }
.list-item-left i { font-size: 18px; color: #000; }
.list-item-right { display: flex; align-items: center; color: #999; }
.theme-segment { display: inline-flex; background: #F1F3F5; border: 1px solid #E5E5E5; border-radius: 999px; padding: 2px; }
.theme-segment button { border: none; background: transparent; color: #666; padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 900; }
.theme-segment button.active { background: #000; color: #fff; }

.cloth-detail-overlay { position: fixed; inset: 0; z-index: 20000; background: rgba(0, 0, 0, 0.55); display: flex; align-items: center; justify-content: center; padding: calc(20px + env(safe-area-inset-top)) 18px calc(20px + env(safe-area-inset-bottom)); overscroll-behavior: contain; }
.cloth-detail-modal { width: min(100%, 420px); max-height: 88svh; background: #fff; color: #000; border-radius: 22px; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; position: relative; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28); display: flex; flex-direction: column; }
.modal-close-btn { position: absolute; top: 12px; right: 12px; z-index: 2; width: 36px; height: 36px; border-radius: 50%; border: none; background: rgba(0, 0, 0, 0.72); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.cloth-detail-image { width: 100%; aspect-ratio: 1 / 1; background: #F1F3F5; overflow: hidden; }
.cloth-detail-image img { width: 100%; height: 100%; object-fit: cover; }
.cloth-detail-content { padding: 18px; text-align: left; }
.cloth-detail-type { display: inline-flex; background: #000; color: #fff; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 900; margin-bottom: 10px; }
.cloth-detail-content h3 { margin: 0 0 12px; font-size: 20px; line-height: 1.25; font-weight: 900; }
.cloth-detail-meta { display: flex; flex-wrap: wrap; gap: 8px; }
.cloth-detail-meta span { display: inline-flex; align-items: center; gap: 4px; background: #F1F3F5; color: #555; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 800; }
.pairing-section { margin-top: 18px; border-top: 1px solid #EEF0F2; padding-top: 14px; }
.pairing-title-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.pairing-title-row h4 { margin: 0; font-size: 14px; font-weight: 900; }
.pairing-title-row span { color: #888; font-size: 11px; font-weight: 800; }
.pairing-grid { display: flex; gap: 10px; overflow-x: auto; overscroll-behavior-x: contain; padding-bottom: 4px; }
.pairing-grid::-webkit-scrollbar { display: none; }
.pairing-card { flex: 0 0 116px; min-width: 0; border: 1px solid #EEF0F2; background: #fff; color: #111; border-radius: 14px; padding: 7px; text-align: left; cursor: pointer; transition: transform 0.18s ease, border-color 0.18s ease; }
.pairing-card:active { transform: scale(0.98); }
.pairing-card img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 10px; background: #F1F3F5; margin-bottom: 7px; }
.pairing-card span { display: block; font-size: 12px; font-weight: 900; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pairing-card small { display: block; color: #777; font-size: 10px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cloth-modal-enter-active,
.cloth-modal-leave-active { transition: opacity 0.24s ease; }
.cloth-modal-enter-active .cloth-detail-modal,
.cloth-modal-leave-active .cloth-detail-modal { transition: transform 0.26s cubic-bezier(0.2, 0.85, 0.25, 1), opacity 0.22s ease; }
.cloth-modal-enter-from,
.cloth-modal-leave-to { opacity: 0; }
.cloth-modal-enter-from .cloth-detail-modal { opacity: 0; transform: translateY(18px) scale(0.96); }
.cloth-modal-leave-to .cloth-detail-modal { opacity: 0; transform: translateY(10px) scale(0.98); }

.app-dialog-overlay { position: fixed; inset: 0; z-index: 30000; display: flex; align-items: center; justify-content: center; padding: 24px 20px calc(24px + env(safe-area-inset-bottom)); background: rgba(0, 0, 0, 0.42); backdrop-filter: blur(10px); }
.app-dialog-card { width: min(100%, 360px); background: rgba(255, 255, 255, 0.96); color: #08090B; border: 1px solid rgba(255, 255, 255, 0.72); border-radius: 22px; padding: 22px; text-align: left; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22); }
.app-dialog-icon { width: 46px; height: 46px; border-radius: 16px; display: flex; align-items: center; justify-content: center; margin-bottom: 16px; font-size: 24px; }
.app-dialog-icon.dialog-success { background: #000; color: #fff; }
.app-dialog-icon.dialog-info { background: #F1F3F5; color: #111; }
.app-dialog-icon.dialog-warning { background: #111; color: #00FF66; }
.app-dialog-content { display: grid; gap: 7px; }
.app-dialog-kicker { color: #777; font-size: 11px; font-weight: 900; letter-spacing: 0.08em; text-transform: uppercase; }
.app-dialog-content h3 { margin: 0; font-size: 21px; font-weight: 950; letter-spacing: 0; }
.app-dialog-content p:last-child { color: #555; font-size: 13px; line-height: 1.65; }
.app-dialog-actions { display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 20px; }
.app-dialog-actions.has-cancel { grid-template-columns: 1fr 1.1fr; }
.dialog-btn { border: none; border-radius: 999px; padding: 12px 14px; font-size: 13px; font-weight: 950; cursor: pointer; }
.dialog-btn-primary { background: #000; color: #fff; }
.dialog-btn-ghost { background: #F1F3F5; color: #111; }
.app-dialog-enter-active,
.app-dialog-leave-active { transition: opacity 0.2s ease; }
.app-dialog-enter-active .app-dialog-card,
.app-dialog-leave-active .app-dialog-card { transition: transform 0.24s cubic-bezier(0.2, 0.85, 0.25, 1), opacity 0.2s ease; }
.app-dialog-enter-from,
.app-dialog-leave-to { opacity: 0; }
.app-dialog-enter-from .app-dialog-card { opacity: 0; transform: translateY(12px) scale(0.97); }
.app-dialog-leave-to .app-dialog-card { opacity: 0; transform: translateY(8px) scale(0.98); }

.app-nav-bar {
  position: fixed; bottom: 0; left: 0; width: 100%; min-width: 0; height: calc(68px + env(safe-area-inset-bottom));
  background: #FFFFFF; border-top: 1px solid #EEF0F2; display: flex; flex-direction: row !important; justify-content: space-around; align-items: center; z-index: 9999; box-sizing: border-box; padding-bottom: env(safe-area-inset-bottom);
}
.nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #7F7F7F; cursor: pointer; height: 100%; transition: all 0.15s ease; }
.icon-wrapper { position: relative; display: inline-block; margin-bottom: 3px; }
.nav-item i { font-size: 22px; transition: all 0.15s ease; }
.nav-item span { font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }
.nav-item.active { color: #000000; }
.nav-item.active i { font-weight: bold; transform: scale(1.05); }
.dot-badge { display: none; }
.count-badge { display: none; }

.animate-pulse-slow { animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
.fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

.theme-dark { background: #0F1115; color: #F4F6FA; }
.theme-dark .app-header,
.theme-dark .weather-card,
.theme-dark .quick-card,
.theme-dark .calendar-header-card,
.theme-dark .week-card,
.theme-dark .history-detail-panel,
.theme-dark .match-input-box,
.theme-dark .ai-match-result-card,
.theme-dark .common-card-rounded,
.theme-dark .cloth-card,
.theme-dark .search-bar-wrap,
.theme-dark .f-tag,
.theme-dark .scene-tag,
.theme-dark .mini-outline-btn,
.theme-dark .app-nav-bar {
  background: #171A20;
  border-color: #2A303A;
  color: #F4F6FA;
}
.theme-dark .ai-recommendation,
.theme-dark .match-hero,
.theme-dark .ai-camera-entry {
  background: #050507 !important;
  border-color: #242A33;
}
.theme-dark .badge,
.theme-dark .random-btn,
.theme-dark .action-btn-full,
.theme-dark .f-tag.active,
.theme-dark .scene-tag.active,
.theme-dark .week-day-cell.selected,
.theme-dark .theme-segment button.active {
  background: #F4F6FA;
  color: #050507;
  border-color: #F4F6FA;
}
.theme-dark .theme-toggle,
.theme-dark .action-btn-sm {
  background: #242A33;
  border-color: #333B48;
  color: #F4F6FA;
}
.theme-dark .city-chip,
.theme-dark .history-card-active,
.theme-dark .match-reason-list div,
.theme-dark .week-day-cell,
.theme-dark .theme-segment,
.theme-dark .cloth-detail-modal,
.theme-dark .cloth-img-wrapper,
.theme-dark .mini-img-wrap,
.theme-dark .avatar-circle,
.theme-dark .cloth-tag-season,
.theme-dark .score-badge,
.theme-dark .empty-state {
  background: #20252E;
  border-color: #303744;
  color: #D8DDE6;
}
.theme-dark .search-bar-wrap input {
  color: #F4F6FA;
  caret-color: #F4F6FA;
  -webkit-text-fill-color: #F4F6FA;
}
.theme-dark .search-bar-wrap input::placeholder {
  color: #8F98A8;
  -webkit-text-fill-color: #8F98A8;
}
.theme-dark .brand small,
.theme-dark .weather-info p,
.theme-dark .quick-card p,
.theme-dark .section-title-row p,
.theme-dark .calendar-subtext,
.theme-dark .week-title,
.theme-dark .week-day-cell span,
.theme-dark .week-day-cell em,
.theme-dark .calendar-note,
.theme-dark .match-hero p,
.theme-dark .match-toolbar p,
.theme-dark .match-score,
.theme-dark .match-desc,
.theme-dark .badge-type,
.theme-dark .match-reason-list div,
.theme-dark .list-item-right,
.theme-dark .common-card-rounded p {
  color: #AAB2C0 !important;
}
.theme-dark .quick-card i,
.theme-dark .list-item-left i,
.theme-dark .empty-state i,
.theme-dark .match-score strong,
.theme-dark .nav-item.active,
.theme-dark .nav-item.active i {
  color: #F4F6FA;
}
.theme-dark .nav-item { color: #7F8998; }
.theme-dark .list-item { border-color: #2A303A; }
.theme-dark .history-item-tag { background: #20252E; border-color: #303744; color: #F4F6FA; }
.theme-dark .cloth-card.background-selected { border-color: #F4F6FA; box-shadow: 0 0 0 3px rgba(244, 246, 250, 0.12), 0 10px 24px rgba(0, 0, 0, 0.28); }
.theme-dark .cloth-detail-modal { color: #F4F6FA; }
.theme-dark .cloth-detail-type { background: #F4F6FA; color: #050507; }
.theme-dark .cloth-detail-meta span { background: #171A20; color: #D8DDE6; }
.theme-dark .pairing-card { background: #171A20; border-color: #303744; color: #F4F6FA; }
.theme-dark .pairing-card small,
.theme-dark .pairing-title-row span { color: #AAB2C0; }
.theme-dark .cloud-warning { background: #2A2110; border-color: #5A4218; color: #FFD88A; }
.theme-dark .app-dialog-overlay { background: rgba(0, 0, 0, 0.58); }
.theme-dark .app-dialog-card { background: rgba(23, 26, 32, 0.96); color: #F4F6FA; border-color: #303744; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.46); }
.theme-dark .app-dialog-icon.dialog-success { background: #F4F6FA; color: #050507; }
.theme-dark .app-dialog-icon.dialog-info { background: #242A33; color: #F4F6FA; }
.theme-dark .app-dialog-icon.dialog-warning { background: #050507; color: #00FF66; }
.theme-dark .app-dialog-kicker,
.theme-dark .app-dialog-content p:last-child { color: #AAB2C0; }
.theme-dark .dialog-btn-primary { background: #F4F6FA; color: #050507; }
.theme-dark .dialog-btn-ghost { background: #242A33; color: #D8DDE6; }

@media (max-width: 360px) {
  .page-content { padding: 12px; gap: 12px; }
  .app-header { padding-left: 12px; padding-right: 12px; }
  .badge { font-size: 9px; padding: 4px 8px; }
  .quick-cards-grid { gap: 8px; }
  .quick-card h4 { font-size: 12px; }
  .cloth-info { padding: 10px; }
  .mini-img-wrap { height: 96px; }
  .nav-item span { font-size: 9px; }
  .header-status { gap: 5px; }
  .theme-toggle { padding: 4px 7px; }
  .match-toolbar { align-items: flex-start; flex-direction: column; }
  .random-btn { width: 100%; justify-content: center; }
}
</style>
