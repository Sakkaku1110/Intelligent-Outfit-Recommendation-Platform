<template>
  <div class="clothes-app-dark">
    <div v-if="showRadar" class="radar-overlay fade-in">
      <div class="radar-box">
        <div class="radar-sweep"></div>
        <i class="ri-radar-line radar-icon"></i>
      </div>
      <h3>海鸥派中央雷达</h3>
      <p class="animate-pulse-slow">正在全仓扫描物理硬件定位 LED 节点...</p>
    </div>

    <header class="app-header">
      <div class="brand">
        <i class="ri-cpu-line"></i>
        <span>ClothesAI <small>衣智柜</small></span>
      </div>
      <div class="header-status">
        <span class="badge">海鸥派 NPU 在线</span>
      </div>
    </header>

    <main class="app-body">
      
      <section v-if="activeTab === 'home'" class="page-content fade-in">
        <div class="weather-card capsule-card">
          <div class="weather-info">
            <i class="ri-sun-cloudy-line weather-icon"></i>
            <div>
              <h3>24°C / 晴</h3>
              <p>早上好, Williams. 今天是 {{ currentYear }}年{{ currentMonth }}月{{ currentDay }}日，适合穿短袖衬衫加薄外套。</p>
            </div>
          </div>
        </div>

        <div class="ai-recommendation capsule-card">
          <div class="recommend-content">
            <span class="tag-ai">AI 穿搭决策</span>
            <h2>今日出行最佳推荐</h2>
            <div class="outfit-preview">
              <div class="cloth-item-mini"><i class="ri-shirt-line"></i> 科技青工装衬衫</div>
              <div class="cloth-item-mini"><i class="ri-t-shirt-line"></i> 莫兰迪灰内搭</div>
            </div>
            <div class="recommend-footer">
              <span>🔥 搭配评分：98分 (舒适度高)</span>
              <button class="action-btn-sm" @click="saveCurrentToCalendar()">保存到今天日历</button>
            </div>
          </div>
        </div>

        <div class="quick-cards-grid">
          <div class="quick-card" @click="activeTab = 'wardrobe'">
            <i class="ri-door-closed-line"></i>
            <h4>我的衣柜</h4>
            <p>15件单品</p>
          </div>
          <div class="quick-card" @click="activeTab = 'calendar'">
            <i class="ri-calendar-check-line"></i>
            <h4>穿搭日历</h4>
            <p>{{ Object.keys(calendarHistory).length }} 条记录</p>
          </div>
          <div class="quick-card" @click="triggerFindCloth">
            <i class="ri-radar-line"></i>
            <h4>快速找衣</h4>
            <p>灯光定位</p>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'wardrobe'" class="page-content fade-in">
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
            v-for="cat in ['全部', '卫衣/针织', '夹克/皮衣', '日常裤装', '衬衫/T恤']" 
            :key="cat"
            class="f-tag"
            :class="{ active: selectedCategory === cat }"
            @click="selectedCategory = cat"
          >
            {{ cat }}
          </span>
        </div>
        
        <div class="clothes-grid">
          <div 
            class="cloth-card" 
            :class="{ 'hardware-glowing': activeHardwareLightId === item.id }" 
            v-for="item in filteredClothes" 
            :key="item.id"
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
              <button class="action-btn-full" style="margin-top: 10px; padding: 8px; font-size: 12px; border-radius: 6px;" @click="triggerHardwareLight(item.id)">
                <i class="ri-lightbulb-flash-line"></i> 一键找衣
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'match'" class="page-content fade-in">
        <div class="match-input-box">
          <h4>💡 选择穿搭场景 / 唤醒海鸥 AI</h4>
          <div class="voice-input-mock">
            <i class="ri-mic-line animate-pulse-slow"></i>
            <span>"海鸥海鸥，推荐一套 {{ currentScene }} 穿搭"</span>
          </div>
          <div class="scene-tags">
            <span class="scene-tag" :class="{ active: currentScene === '上班' }" @click="currentScene = '上班'">上班</span>
            <span class="scene-tag" :class="{ active: currentScene === '约会' }" @click="currentScene = '约会'">约会</span>
            <span class="scene-tag" :class="{ active: currentScene === '旅行' }" @click="currentScene = '旅行'">旅行</span>
            <span class="scene-tag" :class="{ active: currentScene === '运动' }" @click="currentScene = '运动'">运动</span>
          </div>
        </div>

        <div class="ai-match-result-card fade-in" :key="currentScene">
          <div class="match-card-header">
            <span class="ai-badge-neon">NPU 边缘决策</span>
            <div class="match-score">💡 匹配度 <strong>{{ sceneMatches[currentScene].score }}</strong> 分</div>
          </div>
          
          <h3 class="match-title">{{ sceneMatches[currentScene].title }}</h3>
          <p class="match-desc">{{ sceneMatches[currentScene].desc }}</p>
          
          <div class="match-items-row">
            <div class="match-item-mini" v-for="cloth in sceneMatches[currentScene].items" :key="cloth.id">
              <div class="mini-img-wrap">
                <img :src="cloth.img" alt="衣服" />
              </div>
              <div class="mini-meta">
                <span>{{ cloth.name }}</span>
                <small class="badge-type">{{ cloth.type }}</small>
              </div>
            </div>
          </div>

          <button class="action-btn-full" style="border-radius: 8px;" @click="handleApplyOutfit(currentScene)">
            <i class="ri-check-double-line"></i> 采纳这套并同步到穿搭日历
          </button>
        </div>
      </section>

      <section v-if="activeTab === 'calendar'" class="page-content fade-in">
        <div class="calendar-header-card">
          <div class="calendar-month-title">
            <i class="ri-calendar-event-line"></i>
            <h3>{{ currentYear }} 年 {{ currentMonth }} 月</h3>
          </div>
          <p class="calendar-subtext">任意点击空白日期，系统大模型将自动模拟追溯补齐当天的穿搭日志</p>
        </div>

        <div class="calendar-grid-box">
          <div class="weekday-row">
            <span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>
          </div>
          <div class="days-grid">
            <div 
              v-for="emptyCell in firstDayWeeksOffset" 
              :key="'empty-' + emptyCell" 
              class="day-cell empty"
            ></div>
            
            <div 
              v-for="day in totalDaysInMonth" 
              :key="day" 
              class="day-cell"
              :class="{ 
                'has-data': calendarHistory[day], 
                'selected': selectedCalendarDay === day,
                'today': day === currentDay
              }"
              @click="selectDay(day)"
            >
              <span class="day-num">{{ day }}</span>
              <div v-if="calendarHistory[day]" class="data-dot"></div>
            </div>
          </div>
        </div>

        <div class="history-detail-panel fade-in" :key="selectedCalendarDay">
          <h4>📅 {{ selectedCalendarDay }} 日穿搭日志</h4>
          
          <div v-if="calendarHistory[selectedCalendarDay]" class="history-card-active">
            <div class="history-badge-row">
              <span class="scene-badge">{{ calendarHistory[selectedCalendarDay].scene }}场景</span>
              <span class="score-badge">评分: {{ calendarHistory[selectedCalendarDay].score }}分</span>
            </div>
            <h5>{{ calendarHistory[selectedCalendarDay].title }}</h5>
            <p style="font-size: 11px; color: #888; margin: -4px 0 10px 0;">💡 点击下方服装纽扣，可直接激活物理衣柜定位亮灯：</p>
            
            <div class="history-items-list">
              <div 
                class="history-item-tag interactable-tag" 
                v-for="(itemName, idx) in calendarHistory[selectedCalendarDay].items" 
                :key="idx"
                @click="triggerHardwareLightByName(itemName)"
              >
                <i class="ri-lightbulb-flash-line"></i> {{ itemName }}
              </div>
            </div>
          </div>
          <div v-else class="no-data-placeholder">
            <p>该日期暂无穿搭数据，点击格子可自动模拟追溯生成</p>
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
            <h4 style="font-size: 20px;">15</h4>
            <p style="margin-top: 4px;">数字单品</p>
          </div>
          <div class="quick-card">
            <h4 style="font-size: 20px;">{{ Object.keys(calendarHistory).length }}</h4>
            <p style="margin-top: 4px;">穿搭日志</p>
          </div>
        </div>

        <div class="common-card-rounded" style="padding: 4px 20px;">
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

    <nav class="app-nav-bar">
      <div class="nav-item" :class="{ active: activeTab === 'home' }" @click="activeTab = 'home'">
        <div class="icon-wrapper">
          <i class="ri-home-5-line"></i>
          <span class="dot-badge"></span>
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
          <span class="count-badge">{{ Object.keys(calendarHistory).length }}</span>
        </div>
        <span>日历</span>
      </div>
      
      <div class="nav-item" :class="{ active: activeTab === 'me' }" @click="activeTab = 'me'">
        <div class="icon-wrapper">
          <i class="ri-user-line"></i>
          <span class="dot-badge"></span>
        </div>
        <span>我</span>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import 'remixicon/fonts/remixicon.css'

const todayObj = new Date()
const currentYear = ref(todayObj.getFullYear())   
const currentMonth = ref(todayObj.getMonth() + 1) 
const currentDay = ref(todayObj.getDate())        

const activeTab = ref('home')
const selectedCategory = ref('全部')
const searchQuery = ref('')
const selectedCalendarDay = ref(todayObj.getDate())

const totalDaysInMonth = computed(() => {
  return new Date(currentYear.value, currentMonth.value, 0).getDate()
})

const firstDayWeeksOffset = computed(() => {
  let dayOfWeek = new Date(currentYear.value, currentMonth.value - 1, 1).getDay()
  return dayOfWeek === 0 ? 6 : dayOfWeek - 1
})

const calendarHistory = ref({
  1: { scene: '上班', title: '极客通勤：现代极简防风搭配', score: 93, items: ['深空蓝连帽防风外套', '莫兰迪灰微锥直休闲裤'] },
  2: { scene: '约会', title: '都市休闲：温柔轻熟风', score: 95, items: ['燕麦色开襟针织衫 (V领)', '复古白百搭纯T (圆领)'] },
  [todayObj.getDate()]: { scene: '上班', title: '商务通勤：科技感精干风', score: 98, items: ['科技青工装衬衫 (翻领)', '莫兰迪灰微锥直休闲裤'] }
})

const selectDay = (day) => {
  selectedCalendarDay.value = day
  if (!calendarHistory.value[day]) {
    const pool = [
      { scene: '运动', title: '轻量高弹：高街机能穿搭', score: 96, items: ['复古白百搭纯T (圆领)', '夏季高弹轻量透气速干运动短裤'] },
      { scene: '旅行', title: '都市漫游：复古街头工装风', score: 94, items: ['经典水洗蓝单排扣牛仔夹克', '机能风抽绳束脚立体卡其裤'] },
      { scene: '上班', title: '极客通勤：现代极简防风搭配', score: 93, items: ['深空蓝连帽防风外套', '莫兰迪灰微锥直休闲裤'] }
    ]
    calendarHistory.value[day] = pool[day % pool.length]
  }
}

const handleApplyOutfit = (scene) => {
  const data = sceneMatches.value[scene]
  calendarHistory.value[selectedCalendarDay.value] = {
    scene: scene, title: data.title, score: data.score, items: data.items.map(i => i.name)
  }
  alert(`[AI 决策同步] 已将今日“${scene}”穿搭成功记录到 ${currentMonth.value}月${selectedCalendarDay.value}日 的穿搭日历中！`)
  activeTab.value = 'calendar'
}

const saveCurrentToCalendar = () => {
  calendarHistory.value[currentDay.value] = { 
    scene: '上班', title: '商务通勤：科技感精干风', score: 98, items: ['科技青工装衬衫 (翻领)', '莫兰迪灰微锥直休闲裤'] 
  }
  alert(`已将首页推荐成功同步至今日 (${currentDay.value}日) 穿搭日历！`)
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
  { id: 15, name: '夏季高弹轻量透气速干运动短裤', type: '日常裤装', season: '夏季', color: '黑色', count: 22, img: 'https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=300&q=80' }
])

const filteredClothes = computed(() => {
  return mockClothes.value.filter(cloth => {
    const matchCategory = selectedCategory.value === '全部' || cloth.type === selectedCategory.value
    const query = searchQuery.value.trim().toLowerCase()
    return matchCategory && (!query || cloth.name.toLowerCase().includes(query) || cloth.color.toLowerCase().includes(query))
  })
})

const showRadar = ref(false)
const activeHardwareLightId = ref(0)
const triggerFindCloth = () => {
  showRadar.value = true
  setTimeout(() => { showRadar.value = false; activeTab.value = 'wardrobe'; activeHardwareLightId.value = 1 }, 1500)
}

const triggerHardwareLightByName = (name) => {
  const cleanName = name.split(' ')[0]
  const found = mockClothes.value.find(c => c.name.includes(cleanName))
  if (found) {
    activeTab.value = 'wardrobe'
    activeHardwareLightId.value = found.id
    alert(`[MQTT 智能定位] 正在通过日志追踪『${found.name}』，实体货架 LED 硬件灯已同步闪烁！`)
    setTimeout(() => { activeHardwareLightId.value = 0 }, 4000)
  }
}
const triggerCameraMock = () => { alert('[边缘大模型相机已唤醒] 正在调用原生多维 3D 摄像头... 多模态识别接口接通中！') }

const sceneMatches = ref({
  '上班': { title: '商务通勤：科技感精干风', score: 98, desc: '今天有例会，推荐工装衬衫搭配直筒裤。', items: [{ id: 1, name: '科技青工装衬衫 (翻领)', type: '上衣', img: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=300&q=80' }, { id: 2, name: '莫兰迪灰微锥直休闲裤', type: '裤子', img: 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=300&q=80' }] },
  '约会': { title: '都市休闲：温柔轻熟风', score: 95, desc: '温柔的燕麦色是针织开衫，亲和力拉满。', items: [{ id: 6, name: '燕麦色开襟针织衫 (V领)', type: '外套', img: 'https://images.unsplash.com/photo-1614975058789-41316d0e2e9c?auto=format&fit=crop&w=300&q=80' }, { id: 4, name: '复古白百搭纯T (圆领)', type: '上衣', img: 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=300&q=80' }] },
  '旅行': { title: '户外探索：山系机能风', score: 92, desc: '出行防风必不可少，防风外套配工装裤。', items: [{ id: 3, name: '深空蓝连帽防风外套', type: '外套', img: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=300&q=80' }, { id: 5, name: '暗黑系多口袋修身工装裤', type: '裤子', img: 'https://images.unsplash.com/photo-1517423568366-8b83523034fd?auto=format&fit=crop&w=300&q=80' }] },
  '运动': { title: '轻量高弹：高街机能风', score: 96, desc: '高强度运动首选，速干运动短裤无拘无束释放活力。', items: [{ id: 4, name: '复古白百搭纯T (圆领)', type: '上衣', img: 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=300&q=80' }, { id: 15, name: '夏季高弹轻量透气速干运动短裤', type: '日常裤装', img: 'https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=300&q=80' }] }
})
</script>

<style>
/* ==========================================
   DEWU 潮流方圆并济高级皮肤
   ========================================== */
.clothes-app-dark {
  max-width: 412px; min-height: 100vh; margin: 0 auto; background: #F8F9FA; display: flex; flex-direction: column;
  padding-bottom: 120px; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #000000; position: relative;
}
.app-header { background: #FFFFFF; padding: 16px 20px; border-bottom: 1px solid #EEF0F2; display: flex; justify-content: space-between; align-items: center; }
.brand { display: flex; align-items: center; gap: 8px; font-weight: 900; font-size: 18px; }
.brand small { font-weight: normal; font-size: 11px; color: #888; }
.badge { font-size: 10px; background: #000; color: #fff; padding: 4px 10px; font-weight: bold; border-radius: 20px; }

.page-content { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
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
.weather-icon { font-size: 32px; }
.weather-info h3 { margin: 0; font-size: 18px; font-weight: 900; }
.weather-info p { margin: 4px 0 0 0; font-size: 12px; color: #666; line-height: 1.4; }

.ai-recommendation { background: #000; color: #fff; padding: 22px 20px; text-align: left; }
.tag-ai { background: #fff; color: #000; font-size: 10px; font-weight: 900; padding: 3px 8px; border-radius: 10px; }
.ai-recommendation h2 { margin: 10px 0 14px 0; font-size: 19px; font-weight: 900; }
.outfit-preview { display: flex; gap: 10px; margin: 12px 0; }
.cloth-item-mini { background: rgba(255,255,255,0.1); padding: 6px 14px; font-size: 12px; border-radius: 8px; }
.recommend-footer { display: flex; justify-content: space-between; align-items: center; font-size: 11px; }
.action-btn-sm { background: #fff; color: #000; border: none; padding: 6px 16px; font-weight: 900; cursor: pointer; border-radius: 20px; }

.quick-cards-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.quick-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 16px; padding: 14px 8px; display: flex; flex-direction: column; align-items: center; cursor: pointer; transition: all 0.2s; }
.quick-card:hover { border-color: #000; }
.quick-card i { font-size: 24px; color: #000; margin-bottom: 4px; }
.quick-card h4 { font-size: 13px; font-weight: 700; margin: 0 0 2px 0; }
.quick-card p { font-size: 10px; color: #999; margin: 0; }

.search-bar-wrap { display: flex; align-items: center; padding: 12px 18px; gap: 10px; background: #FFF; border: 1px solid #E5E5E5; border-radius: 30px; }
.search-bar-wrap input { border: none; width: 100%; outline: none; font-size: 13px; background: transparent; }

.filter-tabs { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; }
.filter-tabs::-webkit-scrollbar { display: none; }
.f-tag { padding: 6px 16px; background: #fff; border: 1px solid #e5e5e5; font-size: 12px; cursor: pointer; white-space: nowrap; border-radius: 20px; transition: all 0.2s; }
.f-tag.active { background: #000; color: #fff; border-color: #000; font-weight: bold; }

.clothes-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; min-height: 200px; }
.cloth-card { background: #FFFFFF; border: 1px solid #EEF0F2; border-radius: 16px; overflow: hidden; display: flex; flex-direction: column; position: relative; }
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
.calendar-grid-box { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 20px; padding: 16px; display: flex; flex-direction: column; align-items: center; }
.weekday-row { display: grid; grid-template-columns: repeat(7, 46px); justify-content: center; text-align: center; font-size: 11px; font-weight: bold; color: #999; margin-bottom: 12px; width: 100%; }
.days-grid { display: grid; grid-template-columns: repeat(7, 46px); justify-content: center; row-gap: 12px; width: 100%; }
.day-cell { width: 42px !important; height: 42px !important; border-radius: 50% !important; display: flex !important; flex-direction: column; justify-content: center; align-items: center; position: relative; cursor: pointer; background: #FAFAFA; box-sizing: border-box; margin: 0 auto; border: 1px solid transparent; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.day-cell.empty { background: transparent !important; border: none !important; cursor: default; }
.day-num { font-size: 12px; font-weight: bold; color: #333; line-height: 1; transition: color 0.15s; }
.day-cell.has-data { background: #FFFFFF; border: 1px solid #000000; }
.day-cell.today { box-shadow: inset 0 0 0 2px #00FF66; }
.day-cell.selected { background: #000000 !important; border-color: #000000 !important; }
.day-cell.selected .day-num { color: #FFFFFF !important; }
.data-dot { position: absolute; bottom: 4px; width: 4px; height: 4px; background: #00FF66; border-radius: 50%; }
.day-cell.selected .data-dot { background: #00FF66; box-shadow: 0 0 6px #00FF66; }

.history-detail-panel { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 20px; padding: 16px; text-align: left; }
.history-detail-panel h4 { margin: 0 0 12px 0; font-size: 14px; font-weight: 900; }
.history-card-active { background: #F8F9FA; border: 1px solid #EEF0F2; border-radius: 12px; padding: 14px; }
.history-badge-row { display: flex; gap: 8px; margin-bottom: 8px; }
.scene-badge { font-size: 10px; background: #000; color: #fff; padding: 2px 6px; font-weight: bold; border-radius: 4px; }
.score-badge { font-size: 10px; background: #EEE; color: #333; padding: 2px 6px; font-weight: bold; border-radius: 4px; }
.history-card-active h5 { margin: 0 0 10px 0; font-size: 13px; font-weight: 800; }
.history-items-list { display: flex; flex-wrap: wrap; gap: 8px; }
.no-data-placeholder { text-align: center; padding: 20px; color: #999; font-size: 12px; }

.interactable-tag { font-size: 11px; background: #FFF; border: 1px solid #E5E5E5; padding: 6px 12px; border-radius: 8px; display: flex; align-items: center; gap: 6px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
.interactable-tag:hover { background: #000000; color: #FFFFFF; border-color: #000000; transform: translateY(-1px); }
.interactable-tag i { color: #FF2442; }
.interactable-tag:hover i { color: #00FF66; }

.match-input-box { padding: 20px; text-align: left; border: 1px solid #000; background: #fff; }
.match-input-box h4 { margin: 0 0 12px 0; font-size: 14px; font-weight: 900; }
.voice-input-mock { background: #F8F9FA; border: 1px solid #E5E5E5; padding: 12px; display: flex; align-items: center; gap: 10px; font-size: 13px; border-radius: 12px; }
.scene-tags { display: flex; gap: 8px; margin-top: 14px; }
.scene-tag { padding: 6px 16px; font-size: 12px; font-weight: 700; background: #fff; border: 1px solid #E5E5E5; cursor: pointer; border-radius: 20px; transition: all 0.2s; }
.scene-tag.active { background: #000; color: #fff; border-color: #000; }
.ai-match-result-card { border: 1px solid #E5E5E5; padding: 20px; background: #FFFFFF; border-radius: 20px; }
.match-card-header { display: flex; justify-content: space-between; align-items: center; }
.ai-badge-neon { font-size: 10px; font-weight: 900; background: #000; color: #fff; padding: 3px 8px; border-radius: 4px; }
.match-score { font-size: 12px; color: #666; }
.match-score strong { font-size: 18px; color: #000; }
.match-title { margin: 16px 0 8px 0; font-size: 16px; font-weight: 900; text-align: left; }
.match-desc { font-size: 13px; color: #666; line-height: 1.5; margin: 0 0 16px 0; text-align: left; }
.match-items-row { display: flex; gap: 12px; }
.match-item-mini { flex: 1; border: 1px solid #EEF0F2; border-radius: 12px; overflow: hidden; }
.mini-img-wrap { height: 110px; background: #F1F3F5; }
.mini-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.mini-meta { padding: 8px; text-align: left; }
.mini-meta span { font-size: 12px; font-weight: 700; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.action-btn-full { width: 100%; background: #000; color: #fff; border: none; padding: 12px; font-weight: 900; font-size: 13px; cursor: pointer; margin-top: 16px; }
.common-card-rounded { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 16px; padding: 20px; text-align: left; }
.avatar-circle { width: 50px; height: 50px; background: #F1F3F5; border: 1px solid #E5E5E5; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 24px; }

/* 🌟 “我”页面的专属列表项样式 */
.list-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid #EEF0F2; cursor: pointer; transition: all 0.2s; }
.list-item:hover { opacity: 0.7; }
.list-item-left { display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; }
.list-item-left i { font-size: 18px; color: #000; }
.list-item-right { display: flex; align-items: center; color: #999; }

.app-nav-bar {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: 100%; max-width: 412px; height: 68px;
  background: #FFFFFF; border-top: 1px solid #EEF0F2; display: flex; flex-direction: row !important; justify-content: space-around; align-items: center; z-index: 9999; box-sizing: border-box; padding-bottom: env(safe-area-inset-bottom);
}
.nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #7F7F7F; cursor: pointer; height: 100%; transition: all 0.15s ease; }
.icon-wrapper { position: relative; display: inline-block; margin-bottom: 3px; }
.nav-item i { font-size: 22px; transition: all 0.15s ease; }
.nav-item span { font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }
.nav-item.active { color: #000000; }
.nav-item.active i { font-weight: bold; transform: scale(1.05); }
.dot-badge { position: absolute; top: -2px; right: -4px; width: 7px; height: 7px; background-color: #FF2442; border-radius: 50%; border: 1px solid #FFFFFF; }
.count-badge { position: absolute; top: -5px; right: -9px; background-color: #FF2442; color: #FFFFFF; font-size: 9px; font-weight: 900; min-width: 14px; height: 14px; padding: 0 3px; border-radius: 10px; display: flex; justify-content: center; align-items: center; border: 1px solid #FFFFFF; font-family: "Impact", sans-serif; box-sizing: border-box; }

.radar-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: #FFFFFF; z-index: 999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: #000000; }
.radar-box { width: 100px; height: 100px; border: 1px solid #000000; border-radius: 50%; position: relative; display: flex; justify-content: center; align-items: center; margin-bottom: 24px; overflow: hidden; }
.radar-sweep { position: absolute; width: 100%; height: 100%; background: conic-gradient(from 0deg, rgba(0, 0, 0, 0.15) 0deg, transparent 90deg); border-radius: 50%; animation: radar-spin 1.5s linear infinite; }
@keyframes radar-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.radar-icon { font-size: 32px; color: #000000; z-index: 2; }
.radar-overlay h3 { font-size: 18px; font-weight: 900; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 1px;}
.radar-overlay p { font-size: 12px; color: #666666; margin: 0; }

.cloth-card.hardware-glowing { border: 1px solid #00FF66 !important; box-shadow: 0 0 20px rgba(0, 255, 102, 0.2) !important; animation: dewu-blink 0.8s infinite alternate; }
@keyframes dewu-blink { 0% { transform: scale(1); border-radius: 16px; } 100% { transform: scale(1.02); border-color: #000000 !important; border-radius: 16px; } }

.animate-pulse-slow { animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
.fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
</style>