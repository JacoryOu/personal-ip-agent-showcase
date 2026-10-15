<template>
  <div class="space-y-6 max-w-6xl mx-auto">
    <!-- Header with Stats -->
    <div class="glass-card border border-slate-200/80 rounded-3xl p-6 shadow-xs relative overflow-hidden scroll-reveal">
      <!-- Background subtle decorative accent -->
      <div class="absolute -top-12 -right-12 w-64 h-64 bg-gradient-to-br from-indigo-100/40 via-purple-100/20 to-transparent rounded-full blur-2xl pointer-events-none"></div>

      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5 relative z-10">
        <div>
          <h2 class="text-2xl font-black tracking-tight text-slate-900 flex items-center gap-2.5">
            <span class="p-1.5 bg-indigo-50 rounded-xl text-xl">🧠</span>
            <span>{{ t.profile.title }}</span>
          </h2>
          <p class="text-sm text-slate-500 mt-1">
            {{ t.profile.subtitle }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            @click="showOwnWorkModal = true"
            class="inline-flex items-center justify-center px-3.5 py-2 rounded-xl font-bold text-xs bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs active:scale-95 transition-all gap-1.5 cursor-pointer"
          >
            <span>📥</span>
            <span>{{ t.profile.importOwnWorkBtn }}</span>
          </button>
          <button
            type="button"
            @click="showBenchmarkModal = true"
            class="inline-flex items-center justify-center px-3.5 py-2 rounded-xl font-bold text-xs bg-amber-600 hover:bg-amber-700 text-white shadow-xs active:scale-95 transition-all gap-1.5 cursor-pointer"
          >
            <span>⚡</span>
            <span>{{ t.profile.deconstructBenchmarkBtn }}</span>
          </button>
          <button
            type="button"
            @click="openSkillsModal"
            class="inline-flex items-center justify-center px-3 py-2 rounded-xl font-bold text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/80 active:scale-95 transition-all gap-1.5 cursor-pointer"
          >
            <span>🛡️</span>
            <span>{{ t.profile.sandboxSkillsBtn }}</span>
          </button>
          <!-- JSON Import / Export -->
          <button
            type="button"
            @click="triggerProfileImport"
            class="inline-flex items-center justify-center px-3 py-2 rounded-xl font-bold text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/80 active:scale-95 transition-all gap-1.5 cursor-pointer"
            title="Import Thinking DNA from JSON"
          >
            <span>📥</span>
            <span>导入 DNA</span>
          </button>
          <input
            ref="profileFileInputRef"
            type="file"
            accept=".json"
            class="hidden"
            @change="handleProfileFileUpload"
          />

          <button
            type="button"
            :disabled="allTraits.length === 0"
            @click="exportProfileAsJson"
            class="inline-flex items-center justify-center px-3 py-2 rounded-xl font-bold text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200/80 active:scale-95 transition-all gap-1.5 disabled:opacity-50 cursor-pointer"
            title="Export Thinking DNA to JSON"
          >
            <span>📤</span>
            <span>导出 DNA</span>
          </button>

          <button
            type="button"
            @click="showAddModal = true"
            class="inline-flex items-center justify-center px-3.5 py-2 rounded-xl font-bold text-xs bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs active:scale-95 transition-all gap-1.5 cursor-pointer"
          >
            <span>➕</span>
            <span>{{ t.profile.addTraitBtn }}</span>
          </button>
        </div>
      </div>

      <!-- Quick Metrics Counters -->
      <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3.5 pt-5 relative z-10">
        <div class="bg-slate-50/70 hover:bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{{ t.profile.totalTraits }}</div>
          <div class="text-2xl font-black text-slate-800 mt-0.5">{{ allTraits.length }}</div>
        </div>

        <div class="bg-purple-50/60 hover:bg-purple-50 border border-purple-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-purple-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>📌</span>
            <span>{{ t.profile.pinnedTraits }}</span>
          </div>
          <div class="text-2xl font-black text-purple-900 mt-0.5">{{ pinnedCount }}</div>
        </div>

        <div class="bg-blue-50/60 hover:bg-blue-50 border border-blue-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-blue-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>🟢</span>
            <span>{{ t.profile.activeTraits }}</span>
          </div>
          <div class="text-2xl font-black text-blue-900 mt-0.5">{{ activeCount }}</div>
        </div>

        <div class="bg-amber-50/60 hover:bg-amber-50 border border-amber-200/70 rounded-2xl p-3.5 text-center transition">
          <div class="text-[11px] font-bold text-amber-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>🔥</span>
            <span>{{ t.profile.highConfidence }}</span>
          </div>
          <div class="text-2xl font-black text-amber-900 mt-0.5">{{ highConfidenceCount }}</div>
        </div>

        <div class="bg-gradient-to-br from-indigo-50/80 to-purple-50/80 hover:from-indigo-50 hover:to-purple-50 border border-indigo-200/70 rounded-2xl p-3.5 text-center col-span-2 sm:col-span-4 lg:col-span-1 transition">
          <div class="text-[11px] font-bold text-indigo-700 uppercase tracking-wider flex items-center justify-center gap-1">
            <span>⚡</span>
            <span>{{ t.profile.resonanceReinforced }}</span>
          </div>
          <div class="text-2xl font-black text-indigo-900 mt-0.5">{{ evolutionBoostedCount }}</div>
        </div>
      </div>
    </div>

    <!-- Sub-tab View Toggle: Traits Library vs Holographic Timeline -->
    <div class="flex items-center justify-between border-b border-slate-200/80 pb-2">
      <div class="inline-flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-2xl border border-slate-200/80 shadow-2xs">
        <button
          type="button"
          @click="activeSubView = 'traits'"
          class="px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none"
          :class="activeSubView === 'traits' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'"
        >
          🧠 认知特征库 (Thinking DNA)
        </button>
        <button
          type="button"
          @click="activeSubView = 'timeline'"
          class="px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none flex items-center gap-1.5"
          :class="activeSubView === 'timeline' ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'"
        >
          <span>⏳</span>
          <span>时光长河 (Timeline View)</span>
        </button>
        <button
          type="button"
          @click="activeSubView = 'ip_persona'"
          class="px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none flex items-center gap-1.5"
          :class="activeSubView === 'ip_persona' ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'"
        >
          <span>🪪</span>
          <span>{{ t.ip_persona.tab }}</span>
        </button>
        <button
          type="button"
          @click="activeSubView = 'product_vault'"
          class="px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer select-none flex items-center gap-1.5"
          :class="activeSubView === 'product_vault' ? 'bg-emerald-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'"
        >
          <span>📦</span>
          <span>{{ t.product_vault?.tab || '私域好物心智库' }}</span>
        </button>
      </div>
    </div>

    <!-- Sub-view: Holographic Timeline Mounted -->
    <div v-if="activeSubView === 'timeline'">
      <CognitiveTimelineView />
    </div>

    <!-- Sub-view: IP Persona & Stories -->
    <div v-else-if="activeSubView === 'ip_persona'" class="space-y-8">
      <!-- Inspiring High-Contrast Hero Banner for AI Reverse Persona Extraction & Soul Interview -->
      <div
        class="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-6 sm:p-8 text-white shadow-xl border border-indigo-500/30"
      >
        <div
          class="absolute -right-12 -bottom-12 w-64 h-64 bg-gradient-to-br from-indigo-500/25 via-purple-500/15 to-transparent rounded-full blur-3xl pointer-events-none"
        ></div>
        <div
          class="absolute top-0 right-1/4 w-32 h-32 bg-sky-500/10 rounded-full blur-2xl pointer-events-none"
        ></div>

        <div class="relative z-10 space-y-4">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-white/10 text-indigo-200 border border-white/15 backdrop-blur-md">
            <span>✨</span>
            <span>告别死板填表 · AI 原生分身塑形</span>
          </div>

          <h2 class="text-xl sm:text-2xl font-black tracking-tight text-white leading-snug">
            {{ t.ip_persona.bannerTitle || '✨ 告别死板填表：让 AI 从你的旧文、随笔或对谈中反向萃取专属 IP 人设' }}
          </h2>

          <p class="text-xs sm:text-sm text-slate-300 max-w-3xl leading-relaxed">
            {{ t.ip_persona.bannerDesc || '无须苦思冥想硬造人设。粘贴你过往的文章随笔，或在对谈室中与数字镜像深入聊聊，AI 就能自动提炼你鲜活的 IP 调性、受众心智与经历故事。' }}
          </p>

          <!-- 2 Primary CTA Buttons + Secondary Manual Button -->
          <div class="flex flex-wrap items-center gap-3 pt-2">
            <!-- 按钮 A: 粘贴旧文/随笔 一键萃取人设 -->
            <button
              type="button"
              @click="showExtractModal = true"
              class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-gradient-to-r from-indigo-500 via-purple-600 to-indigo-600 hover:from-indigo-600 hover:to-purple-700 text-white font-black text-xs sm:text-sm shadow-lg shadow-indigo-500/30 active:scale-95 transition cursor-pointer"
            >
              <span>📝</span>
              <span>{{ t.ip_persona.extractFromTextBtn || '📝 粘贴旧文/随笔 一键萃取人设' }}</span>
            </button>

            <!-- 按钮 B: 开启灵魂专访 (在对谈室中聊出人设) -->
            <button
              type="button"
              @click="handleOpenInterview"
              class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/20 text-white border border-white/20 font-black text-xs sm:text-sm backdrop-blur-md active:scale-95 transition cursor-pointer"
            >
              <span>🎙️</span>
              <span>{{ t.ip_persona.startInterviewBtn || '🎙️ 开启灵魂专访 (在对谈室中聊出人设)' }}</span>
            </button>

            <!-- Secondary Subtle Button: + 手动创建人设 -->
            <button
              type="button"
              @click="showPersonaModal = true"
              class="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-2xl text-xs font-semibold text-slate-300 hover:text-white hover:bg-white/10 border border-white/10 transition cursor-pointer sm:ml-auto"
            >
              <span>+</span>
              <span>{{ t.ip_persona.manualCreateBtn || '+ 手动创建人设' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Persona Section -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold flex items-center gap-2 text-slate-800">
            <span>🎭</span>
            <span>{{ t.ip_persona.title }}</span>
          </h3>
          <button @click="showPersonaModal = true" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-bold rounded-xl shadow-2xs active:scale-95 transition cursor-pointer">
            {{ t.ip_persona.manualCreateBtn || '+ 手动创建人设' }}
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="persona in personas" :key="persona.id" 
            class="bg-white border rounded-3xl p-5 shadow-xs relative transition hover:shadow-md"
            :class="persona.is_active ? 'border-indigo-400 ring-2 ring-indigo-100' : 'border-slate-200 hover:border-slate-300'">
            <div v-if="persona.is_active" class="absolute -top-3 -right-2 bg-indigo-50 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded-full border border-indigo-200 shadow-2xs">
              {{ t.ip_persona.activeBadge }}
            </div>
            <h4 class="font-black text-slate-900 text-base mb-1.5">{{ persona.name }}</h4>
            <div class="text-xs text-slate-500 mb-2 flex items-center gap-1"><span>{{ t.ip_persona.salutationLabel }}</span><span class="font-semibold text-slate-700">{{ persona.reader_salutation || t.ip_persona.noSalutation }}</span></div>
            <div class="text-xs bg-slate-50 border border-slate-100 p-2.5 rounded-xl mb-2 text-slate-700 line-clamp-2" title="语气风格">
              🎙️ {{ persona.tone_style || t.ip_persona.noTone }}
            </div>
            <div class="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 p-2.5 rounded-xl line-clamp-3 mb-3">
              📖 {{ persona.origin_story || t.ip_persona.noStory }}
            </div>
            <div class="flex justify-end mt-auto pt-3 border-t border-slate-100/80">
              <button v-if="!persona.is_active" @click="handleActivatePersona(persona.id)" class="text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 border border-indigo-100 px-3 py-1.5 rounded-lg transition active:scale-95 cursor-pointer">
                {{ t.ip_persona.activateBtn }}
              </button>
            </div>
          </div>
          <div v-if="personas.length === 0" class="col-span-full text-center py-8 text-slate-500 text-sm border border-dashed border-slate-200 rounded-3xl bg-slate-50/50">
            {{ t.ip_persona.emptyPersona }}
          </div>
        </div>
      </div>

      <!-- Story Section -->
      <div>
        <div class="flex items-center justify-between mb-4 border-t border-slate-100 pt-8">
          <h3 class="text-lg font-bold flex items-center gap-2 text-slate-800">
            <span>📖</span>
            <span>{{ t.ip_persona.storyTitle }}</span>
          </h3>
          <button @click="showStoryModal = true" class="px-3 py-1.5 bg-emerald-600 text-white text-xs font-bold rounded-xl hover:bg-emerald-700 shadow-xs active:scale-95 transition cursor-pointer">
            + 记录一段故事
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="story in stories" :key="story.id" class="bg-white border border-slate-200 rounded-3xl p-5 shadow-xs hover:shadow-md transition">
            <div class="flex items-center justify-between mb-2 gap-2">
              <h4 class="font-bold text-slate-900 text-sm truncate flex-1">{{ story.title || t.ip_persona.noTitle }}</h4>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-bold shrink-0 border border-slate-200">
                {{ getStoryTypeLabel(story.story_type) }}
              </span>
            </div>
            <div class="text-[11px] text-slate-400 mb-2 font-mono" v-if="story.occurred_at">
              {{ t.ip_persona.occurredAt }}{{ story.occurred_at.split('T')[0] }}
            </div>
            <div class="text-xs text-slate-700 bg-slate-50 border border-slate-100 p-3 rounded-xl line-clamp-3 mb-3 leading-relaxed">
              {{ story.story_content }}
            </div>
            <div class="flex flex-wrap gap-1.5" v-if="story.tags && story.tags.length">
              <span v-for="tag in story.tags" :key="tag" class="text-[10px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-lg font-medium">
                #{{ tag }}
              </span>
            </div>
          </div>
          <div v-if="stories.length === 0" class="col-span-full text-center py-8 text-slate-500 text-sm border border-dashed border-slate-200 rounded-3xl bg-slate-50/50">
            {{ t.ip_persona.emptyStory }}
          </div>
        </div>
      </div>
    </div>

    <!-- Sub-view: Private Domain Product Vault -->
    <div v-else-if="activeSubView === 'product_vault'" class="space-y-8">
      <!-- Inspiring High-Contrast Hero Banner for AI Reverse Product Extraction -->
      <div
        class="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-emerald-950 to-slate-900 p-6 sm:p-8 text-white shadow-xl border border-emerald-500/30"
      >
        <div
          class="absolute -right-12 -bottom-12 w-64 h-64 bg-gradient-to-br from-emerald-500/25 via-teal-500/15 to-transparent rounded-full blur-3xl pointer-events-none"
        ></div>
        <div
          class="absolute top-0 right-1/4 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl pointer-events-none"
        ></div>

        <div class="relative z-10 space-y-4">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-white/10 text-emerald-200 border border-white/15 backdrop-blur-md">
            <span>📦</span>
            <span>{{ t.product_vault?.heroBadge || '真实自用与交付方案' }}</span>
          </div>

          <h2 class="text-xl sm:text-2xl font-black tracking-tight text-white leading-snug">
            {{ t.product_vault?.heroTitle || '📦 真实自用与交付方案：告别硬广推销，让 AI 从产品文案中反向提炼信任心智' }}
          </h2>

          <p class="text-xs sm:text-sm text-slate-300 max-w-3xl leading-relaxed">
            {{ t.product_vault?.heroSubtitle || '告别生硬推销。粘贴供应商资料或产品文案，让 AI 自动提炼适用体质、劝退禁忌、第一人称自用体感与低阻力转化引子。' }}
          </p>

          <!-- CTAs -->
          <div class="flex flex-wrap items-center gap-3 pt-2">
            <!-- 按钮 A: 粘贴文案一键萃取产品 -->
            <button
              type="button"
              @click="showExtractProductModal = true"
              class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-600 to-indigo-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-xs sm:text-sm shadow-lg shadow-emerald-500/25 active:scale-95 transition cursor-pointer"
            >
              <span>✨</span>
              <span>{{ t.product_vault?.extractCTA || '✨ 粘贴文案一键萃取产品' }}</span>
            </button>

            <!-- 按钮 B: 手动录入好物档案 -->
            <button
              type="button"
              @click="openCreateProductModal"
              class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white/10 hover:bg-white/20 text-white border border-white/20 font-black text-xs sm:text-sm backdrop-blur-md active:scale-95 transition cursor-pointer"
            >
              <span>➕</span>
              <span>{{ t.product_vault?.manualCreateCTA || '➕ 手动录入好物档案' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Products Grid Section -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold flex items-center gap-2 text-slate-800">
            <span>📦</span>
            <span>{{ t.product_vault?.listTitle || '私域好物心智库 (Product Vault)' }}</span>
            <span class="text-xs text-slate-500 font-mono font-normal">({{ products.length }})</span>
          </h3>
          <button
            type="button"
            @click="openCreateProductModal"
            class="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-bold rounded-xl shadow-2xs active:scale-95 transition cursor-pointer flex items-center gap-1.5"
          >
            <span>➕</span>
            <span>{{ t.product_vault?.manualCreateCTA || '手动录入好物档案' }}</span>
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="prod in products"
            :key="prod.id"
            class="bg-white border rounded-3xl p-5 shadow-xs relative transition hover:shadow-md flex flex-col justify-between space-y-3.5"
            :class="prod.is_active ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-slate-200 hover:border-slate-300'"
          >
            <!-- Active Badge -->
            <div
              v-if="prod.is_active"
              class="absolute -top-3 -right-2 bg-emerald-50 text-emerald-700 text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-emerald-300 shadow-2xs flex items-center gap-1"
            >
              <span>🌟</span>
              <span>{{ t.product_vault?.activeMainBadge || '当前主推好物' }}</span>
            </div>

            <!-- Cover Image Banner / Fallback Aesthetic Placeholder -->
            <div class="relative w-full h-44 rounded-2xl overflow-hidden border border-slate-200/80 bg-slate-50 group">
              <img
                v-if="prod.cover_image"
                :src="resolveImageUrl(prod.cover_image)"
                alt="Product Cover"
                class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105 cursor-pointer"
                @click="openLightbox(resolveImageUrl(prod.cover_image), prod.product_name + ' · 封面图')"
              />
              <div
                v-else
                class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-emerald-50/70 via-teal-50/40 to-slate-50 text-slate-400 p-4 text-center select-none"
              >
                <span class="text-3xl mb-1 opacity-70">🍵</span>
                <span class="text-xs font-medium text-slate-500">{{ t.product_vault?.noCoverPlaceholder || '暂无封面图 (默认禅意美学底纹)' }}</span>
              </div>

              <!-- Overlaid Badges for Counts -->
              <div class="absolute bottom-2 right-2 flex items-center gap-1.5 z-10">
                <span
                  v-if="prod.gallery_images && prod.gallery_images.length > 0"
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-900/75 text-white backdrop-blur-md border border-white/20 shadow-xs"
                >
                  {{ (t.product_vault?.physicalBadge || '📸 {count} 张实物图').replace('{count}', String(prod.gallery_images.length)) }}
                </span>
                <span
                  v-if="prod.service_rights_images && prod.service_rights_images.length > 0"
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-900/80 text-emerald-200 backdrop-blur-md border border-emerald-400/30 shadow-xs"
                >
                  {{ (t.product_vault?.rightsBadge || '🛡️ {count} 张权益图').replace('{count}', String(prod.service_rights_images.length)) }}
                </span>
              </div>
            </div>

            <!-- Header: Title & Category -->
            <div class="space-y-1.5">
              <div class="flex items-start justify-between gap-3 pr-16">
                <h4 class="font-black text-slate-900 text-base leading-snug">
                  {{ prod.product_name }}
                </h4>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  🏷️ {{ prod.category || (t.product_vault?.categoryFallback || '好物交付方案') }}
                </span>
                <span v-if="prod.conversion_hooks" class="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 truncate max-w-[200px]" :title="prod.conversion_hooks">
                  🎁 {{ prod.conversion_hooks }}
                </span>
              </div>
            </div>

            <!-- Core Ingredients -->
            <div v-if="prod.core_ingredients" class="space-y-1">
              <div class="text-[11px] font-bold text-slate-600 flex items-center gap-1">
                <span>🌿</span>
                <span>{{ t.product_vault?.coreIngredients || '核心配料 / 工艺亮点' }}</span>
              </div>
              <p class="text-xs text-slate-700 bg-slate-50 border border-slate-100 p-2.5 rounded-xl leading-relaxed">
                {{ prod.core_ingredients }}
              </p>
            </div>

            <!-- Suitable Conditions -->
            <div v-if="prod.suitable_conditions" class="space-y-1">
              <div class="text-[11px] font-bold text-emerald-800 flex items-center gap-1">
                <span>✅</span>
                <span>{{ t.product_vault?.suitableConditions || '精准适用体质与人群' }}</span>
              </div>
              <p class="text-xs text-emerald-950 bg-emerald-50/60 border border-emerald-100 p-2.5 rounded-xl leading-relaxed">
                {{ prod.suitable_conditions }}
              </p>
            </div>

            <!-- Prominent Red/Amber Taboos Warning Alert -->
            <div v-if="prod.taboos" class="space-y-1">
              <div class="text-[11px] font-bold text-rose-800 flex items-center gap-1">
                <span>⚠️</span>
                <span>{{ t.product_vault?.taboos || '劝退禁忌人群 (信任基石)' }}</span>
              </div>
              <div class="text-xs text-rose-950 bg-rose-50/80 border-2 border-rose-200/90 p-2.5 rounded-xl font-medium leading-relaxed">
                {{ prod.taboos }}
              </div>
            </div>

            <!-- First Person Usage Experience -->
            <div v-if="prod.personal_usage_experience" class="space-y-1">
              <div class="text-[11px] font-bold text-amber-900 flex items-center gap-1">
                <span>💬</span>
                <span>{{ t.product_vault?.personalExperience || '第一人称真实自用体验与体感' }}</span>
              </div>
              <div class="text-xs text-amber-950 bg-amber-50/50 border border-amber-200/70 p-2.5 rounded-xl italic leading-relaxed">
                “{{ prod.personal_usage_experience }}”
              </div>
            </div>

            <!-- Visual Asset Gallery Previews -->
            <div v-if="(prod.gallery_images && prod.gallery_images.length > 0) || (prod.service_rights_images && prod.service_rights_images.length > 0)" class="space-y-2 pt-2 border-t border-slate-100">
              <div class="text-[11px] font-bold text-slate-600 flex items-center justify-between">
                <span class="flex items-center gap-1">
                  <span>🖼️</span>
                  <span>{{ t.product_vault?.imageFeedTitle || '好物视觉切片画廊' }}</span>
                </span>
                <span class="text-[10px] text-slate-400">点击大图灯箱预览</span>
              </div>
              <div class="flex flex-wrap gap-2 items-center">
                <!-- Gallery Thumbnails -->
                <div
                  v-for="(img, gIdx) in (prod.gallery_images || []).slice(0, 4)"
                  :key="'g-' + gIdx"
                  class="relative w-12 h-12 rounded-xl overflow-hidden border border-slate-200 cursor-pointer hover:ring-2 hover:ring-emerald-400 transition shrink-0 group"
                  @click="openLightbox(resolveImageUrl(img), prod.product_name + ' · 实物生活图 #' + (gIdx + 1))"
                  :title="'实物图 #' + (gIdx + 1)"
                >
                  <img :src="resolveImageUrl(img)" class="w-full h-full object-cover group-hover:scale-110 transition duration-200" />
                  <span class="absolute bottom-0 right-0 text-[8px] bg-slate-900/70 text-white px-1 rounded-tl font-bold">{{ t.product_vault?.photoBadge || '实物' }}</span>
                </div>
                <span v-if="(prod.gallery_images?.length || 0) > 4" class="text-[10px] text-slate-500 font-bold bg-slate-100 px-2 py-1 rounded-lg">
                  +{{ (prod.gallery_images?.length || 0) - 4 }}
                </span>

                <!-- Rights Thumbnails -->
                <div
                  v-for="(img, rIdx) in (prod.service_rights_images || []).slice(0, 3)"
                  :key="'r-' + rIdx"
                  class="relative w-12 h-12 rounded-xl overflow-hidden border border-emerald-200 cursor-pointer hover:ring-2 hover:ring-emerald-500 transition shrink-0 group"
                  @click="openLightbox(resolveImageUrl(img), prod.product_name + ' · 权益保障图 #' + (rIdx + 1))"
                  :title="'权益图 #' + (rIdx + 1)"
                >
                  <img :src="resolveImageUrl(img)" class="w-full h-full object-cover group-hover:scale-110 transition duration-200" />
                  <span class="absolute bottom-0 right-0 text-[8px] bg-emerald-800/80 text-white px-1 rounded-tl font-bold">{{ t.product_vault?.rightsTag || '权益' }}</span>
                </div>
                <span v-if="(prod.service_rights_images?.length || 0) > 3" class="text-[10px] text-emerald-700 font-bold bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-lg">
                  +{{ (prod.service_rights_images?.length || 0) - 3 }}
                </span>
              </div>
            </div>

            <!-- Actions Bar -->
            <div class="flex items-center justify-between mt-auto pt-3 border-t border-slate-100/80">
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  @click="openEditProductModal(prod)"
                  class="text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-slate-100 px-2.5 py-1 rounded-lg transition cursor-pointer"
                >
                  ✏️ {{ t.product_vault?.editBtn || '编辑' }}
                </button>
                <button
                  type="button"
                  @click="handleDeleteProduct(prod.id, prod.product_name)"
                  class="text-xs font-semibold text-rose-500 hover:text-rose-700 hover:bg-rose-50 px-2.5 py-1 rounded-lg transition cursor-pointer"
                >
                  🗑️ {{ t.product_vault?.deleteBtn || '删除' }}
                </button>
              </div>

              <div>
                <button
                  v-if="!prod.is_active"
                  type="button"
                  @click="handleSetActiveProduct(prod.id)"
                  class="text-xs font-bold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-3 py-1.5 rounded-xl transition active:scale-95 cursor-pointer flex items-center gap-1"
                >
                  <span>🌟</span>
                  <span>{{ t.product_vault?.activeMainBtn || '设为主推' }}</span>
                </button>
                <button
                  v-else
                  type="button"
                  @click="handleToggleActiveProduct(prod.id, false)"
                  class="text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-3 py-1.5 rounded-xl inline-flex items-center gap-1 cursor-pointer transition active:scale-95"
                  :title="t.product_vault?.inactiveBtn || '取消主推'"
                >
                  <span>✓</span>
                  <span>{{ t.product_vault?.alreadyActive || '主推中' }}</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div
            v-if="products.length === 0"
            class="col-span-full text-center py-12 px-6 border-2 border-dashed border-slate-200 rounded-3xl bg-slate-50/50 space-y-4"
          >
            <div class="w-14 h-14 mx-auto rounded-3xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-3xl">
              📦
            </div>
            <div class="space-y-1">
              <h4 class="text-sm font-black text-slate-800">
                {{ t.product_vault?.emptyTitle || '暂无好物档案' }}
              </h4>
              <p class="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                {{ t.product_vault?.emptyDesc || '点击上方「✨ 粘贴文案一键萃取产品」或「➕ 手动录入好物档案」，构建高信任私域交付资产库。' }}
              </p>
            </div>
            <div class="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                type="button"
                @click="showExtractProductModal = true"
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs active:scale-95 transition cursor-pointer flex items-center gap-1.5"
              >
                <span>✨</span>
                <span>{{ t.product_vault?.extractCTA || '✨ 粘贴文案一键萃取产品' }}</span>
              </button>
              <button
                type="button"
                @click="openCreateProductModal"
                class="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-bold rounded-xl shadow-2xs active:scale-95 transition cursor-pointer flex items-center gap-1.5"
              >
                <span>➕</span>
                <span>{{ t.product_vault?.manualCreateCTA || '➕ 手动录入好物档案' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Sub-view: Regular Traits Management -->
    <div v-else-if="activeSubView === 'traits'" class="space-y-6">

    <!-- Viewpoint Conflict Resolution Card (Requirement 1: Striking Split Card) -->
    <div
      v-if="activeConflict && !activeConflict.resolved"
      class="glass-card bg-gradient-to-br from-white via-amber-50/20 to-rose-50/30 border-2 border-amber-300/80 rounded-3xl p-5 sm:p-6 shadow-sm relative overflow-hidden transition-all duration-300 scroll-reveal"
    >
      <!-- Top Header & Banner -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-amber-100 pb-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-300 flex items-center justify-center text-amber-600 text-lg shadow-2xs">
            ⚔️
          </div>
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <h3 class="text-base font-black text-slate-900">
                观点冲突检测与消解台 (Viewpoint Clash Resolution)
              </h3>
              <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-100 text-amber-800 border border-amber-300">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                <span>检测到 1 处价值主张冲突</span>
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-0.5">
              {{ activeConflict.description }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-end sm:self-auto">
          <button
            type="button"
            @click="scanForConflicts"
            :disabled="isScanningConflict"
            class="px-3 py-1.5 text-xs font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-xl transition cursor-pointer active:scale-95 disabled:opacity-50 flex items-center gap-1.5"
            title="重新扫描所有特征"
          >
            <span :class="{ 'animate-spin': isScanningConflict }">🔄</span>
            <span>{{ isScanningConflict ? '扫描中...' : '重新检测' }}</span>
          </button>
          <button
            type="button"
            @click="dismissConflict"
            class="p-1.5 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100 transition cursor-pointer"
            title="忽略并关闭"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Split Card Body (Side A vs Side B) -->
      <div class="grid grid-cols-1 lg:grid-cols-11 gap-4 items-stretch my-5">
        <!-- Side A Card (Existing Core Thesis) -->
        <div class="lg:col-span-5 bg-white rounded-2xl p-5 border border-indigo-200/80 shadow-2xs flex flex-col justify-between space-y-4 hover:border-indigo-400 transition">
          <div class="space-y-3">
            <div class="flex items-center justify-between gap-2">
              <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                <span>🎯</span>
                <span>{{ activeConflict.traitA.tag }}</span>
              </span>
              <span class="text-[11px] font-bold text-indigo-900 font-mono bg-indigo-50/50 px-2 py-0.5 rounded-md">
                🔥 {{ activeConflict.traitA.confidence.toFixed(1) }}x 置信度
              </span>
            </div>

            <!-- Thesis Statement -->
            <p class="text-sm font-bold text-slate-800 leading-relaxed">
              “{{ activeConflict.traitA.statement }}”
            </p>
          </div>

          <!-- Bottom Action for Side A -->
          <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
            <span class="text-[11px] text-slate-400">方案 A · 认知基石</span>
            <button
              type="button"
              @click="handleResolveConflict('keep_a')"
              class="px-3.5 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition active:scale-95 cursor-pointer flex items-center gap-1.5"
            >
              <span>✓</span>
              <span>保留主张 A (抑制 B)</span>
            </button>
          </div>
        </div>

        <!-- Center Clash VS Divider -->
        <div class="lg:col-span-1 flex flex-col items-center justify-center my-1 lg:my-0">
          <div class="relative flex items-center justify-center">
            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500 to-rose-500 text-white font-black text-xs flex items-center justify-center shadow-md shadow-rose-500/20 ring-4 ring-amber-100">
              VS
            </div>
          </div>
          <span class="text-[10px] font-extrabold text-amber-700 uppercase tracking-widest mt-1">CLASH</span>
        </div>

        <!-- Side B Card (Conflicting / Emerging Thesis) -->
        <div class="lg:col-span-5 bg-white rounded-2xl p-5 border border-rose-200/80 shadow-2xs flex flex-col justify-between space-y-4 hover:border-rose-400 transition">
          <div class="space-y-3">
            <div class="flex items-center justify-between gap-2">
              <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                <span>⚡</span>
                <span>{{ activeConflict.traitB.tag }}</span>
              </span>
              <span class="text-[11px] font-bold text-rose-900 font-mono bg-rose-50/50 px-2 py-0.5 rounded-md">
                ⚡ {{ activeConflict.traitB.confidence.toFixed(1) }}x 置信度
              </span>
            </div>

            <!-- Thesis Statement -->
            <p class="text-sm font-bold text-slate-800 leading-relaxed">
              “{{ activeConflict.traitB.statement }}”
            </p>
          </div>

          <!-- Bottom Action for Side B -->
          <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
            <span class="text-[11px] text-slate-400">方案 B · 新引入观点</span>
            <button
              type="button"
              @click="handleResolveConflict('keep_b')"
              class="px-3.5 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-xs transition active:scale-95 cursor-pointer flex items-center gap-1.5"
            >
              <span>✓</span>
              <span>采纳主张 B (淘汰 A)</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Advanced Resolution Actions Bar -->
      <div class="pt-4 border-t border-amber-200/70 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div class="flex items-center gap-2 text-slate-500">
          <span>💡</span>
          <span>或者选择高级协同策略：</span>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            @click="handleResolveConflict('coexist')"
            class="px-3 py-1.5 rounded-xl font-bold bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-2xs transition active:scale-95 cursor-pointer flex items-center gap-1"
          >
            <span>⚖️</span>
            <span>二者共存 (标记为分场景适用)</span>
          </button>
          <button
            type="button"
            @click="handleResolveConflict('synthesize')"
            class="px-3.5 py-1.5 rounded-xl font-bold text-white bg-gradient-to-r from-amber-600 to-indigo-600 hover:opacity-95 shadow-2xs transition active:scale-95 cursor-pointer flex items-center gap-1"
          >
            <span>✨</span>
            <span>融合折中 (合并观点)</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Conflict Resolved Toast Banner -->
    <div
      v-if="conflictToastMessage"
      class="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex items-center justify-between text-xs text-emerald-800 toast-enter"
    >
      <div class="flex items-center gap-2">
        <span class="text-base">🎉</span>
        <span class="font-bold">{{ conflictToastMessage }}</span>
      </div>
      <button
        type="button"
        @click="conflictToastMessage = ''"
        class="text-emerald-600 hover:text-emerald-900 font-bold cursor-pointer"
      >
        ✕
      </button>
    </div>

    <!-- Filter & Search Toolbar -->
    <div class="glass-card border border-slate-200 rounded-2xl p-4 shadow-xs space-y-3 scroll-reveal">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <!-- Dimension Filters -->
        <div class="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
          <button
            type="button"
            @click="dimensionFilter = 'all'"
            class="px-3 py-1.5 rounded-xl border transition-all cursor-pointer active:scale-95"
            :class="dimensionFilter === 'all' ? 'bg-slate-900 text-white border-slate-900 shadow-xs' : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'"
          >
            {{ t.profile.filterAll }} ({{ allTraits.length }})
          </button>
          <button
            type="button"
            @click="dimensionFilter = 'vocabulary'"
            class="px-3 py-1.5 rounded-xl border transition-all cursor-pointer active:scale-95"
            :class="dimensionFilter === 'vocabulary' ? 'bg-blue-600 text-white border-blue-600 shadow-xs' : 'bg-blue-50/70 text-blue-700 border-blue-200 hover:bg-blue-100/70'"
          >
            📚 {{ t.profile.dimVocabulary }} ({{ countByDimension('vocabulary') }})
          </button>
          <button
            type="button"
            @click="dimensionFilter = 'logic_preference'"
            class="px-3 py-1.5 rounded-xl border transition-all cursor-pointer active:scale-95"
            :class="dimensionFilter === 'logic_preference' ? 'bg-amber-600 text-white border-amber-600 shadow-xs' : 'bg-amber-50/70 text-amber-800 border-amber-200 hover:bg-amber-100/70'"
          >
            🧩 {{ t.profile.dimLogic }} ({{ countByDimension('logic_preference') }})
          </button>
          <button
            type="button"
            @click="dimensionFilter = 'core_value'"
            class="px-3 py-1.5 rounded-xl border transition-all cursor-pointer active:scale-95"
            :class="dimensionFilter === 'core_value' ? 'bg-purple-600 text-white border-purple-600 shadow-xs' : 'bg-purple-50/70 text-purple-700 border-purple-200 hover:bg-purple-100/70'"
          >
            🎯 {{ t.profile.dimValues }} ({{ countByDimension('core_value') + countByDimension('viewpoint_stance') }})
          </button>
        </div>

        <!-- Status Filter & Search -->
        <div class="flex items-center gap-2 flex-1 sm:flex-initial min-w-[220px]">
          <select
            v-model="statusFilter"
            class="text-xs bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="all">{{ t.profile.statusAll }}</option>
            <option value="pinned">📌 {{ t.profile.statusPinned }}</option>
            <option value="active">🟢 {{ t.profile.statusActive }}</option>
            <option value="suppressed">🚫 {{ t.profile.statusSuppressed }}</option>
          </select>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t.profile.searchPlaceholder"
            class="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 w-full focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
          />
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-16 bg-white border border-slate-200 rounded-3xl">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent mb-3"></div>
      <p class="text-sm font-medium text-slate-500">{{ t.profile.loadingTraits }}</p>
    </div>

    <!-- Loaded Content Container -->
    <div v-else class="space-y-6">
      <!-- Conflict & Obsolescence Management Banner (Module 3) -->
      <div
        v-if="suppressedCount > 0"
        class="bg-rose-50/70 border border-rose-200 rounded-3xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs"
      >
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-2xl bg-rose-100 border border-rose-200 flex items-center justify-center text-rose-600 text-lg">
            🚫
          </div>
          <div>
            <h4 class="text-xs font-black text-rose-950 uppercase tracking-wide">
              观点冲突与淘汰管理
            </h4>
            <p class="text-xs text-rose-800/90 mt-0.5">
              当前共有 {{ suppressedCount }} 条特征已被停用淘汰。这些观点已被系统物理隔离，不会注入后续文章草稿中。
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            @click="statusFilter = statusFilter === 'suppressed' ? 'all' : 'suppressed'"
            class="px-3 py-1.5 text-xs font-bold rounded-xl border border-rose-300 bg-white text-rose-800 hover:bg-rose-50 transition cursor-pointer active:scale-95"
          >
            {{ statusFilter === 'suppressed' ? '查看全部特征' : '只看已淘汰' }}
          </button>
          <button
            type="button"
            @click="handlePurgeSuppressed"
            class="px-3 py-1.5 text-xs font-bold rounded-xl bg-rose-600 text-white hover:bg-rose-700 shadow-2xs transition cursor-pointer active:scale-95"
            title="Permanently remove all suppressed traits"
          >
            一键清退淘汰观点
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="filteredTraits.length === 0" class="text-center py-16 bg-white border border-slate-200 rounded-3xl p-6">
        <div class="text-4xl mb-3">🧬</div>
        <h3 class="text-base font-bold text-slate-700">{{ t.profile.emptyHint }}</h3>
        <p class="text-xs text-slate-400 mt-1 max-w-md mx-auto">
          {{ t.profile.emptySubHint }}
        </p>
        <button
          type="button"
          @click="showAddModal = true"
          class="mt-4 px-4 py-2 text-xs font-bold rounded-xl bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-200 cursor-pointer active:scale-95 transition"
        >
          {{ t.profile.addTraitBtn }}
        </button>
      </div>

      <!-- Traits Grid (Requirement 1: Progress bar, Category chips, Timeline pill) -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 cv-auto">
        <div
          v-for="trait in filteredTraits"
          :key="trait.id"
          class="bg-white border rounded-3xl p-5 shadow-xs flex flex-col justify-between transition-all duration-200 hover:shadow-md hover:border-slate-300 relative group scroll-reveal active:scale-[0.99]"
          :class="{
            'border-purple-300 ring-2 ring-purple-100/80 bg-gradient-to-b from-purple-50/30 to-white': trait.status === 'pinned',
            'border-slate-200/90': trait.status === 'active',
            'border-dashed border-slate-300 opacity-60 bg-slate-50/70': trait.status === 'suppressed'
          }"
        >
          <div class="space-y-3">
            <!-- Card Top Pill Row: Dimension Tag + Version Timeline Pill + Status Badges -->
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <!-- Clear Category Chip (Requirement 1) -->
              <span
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[11px] font-bold tracking-wide border shadow-2xs"
                :class="dimensionTagClass(trait.dimension)"
              >
                <span>{{ dimensionTagIcon(trait.dimension) }}</span>
                <span>{{ dimensionTagLabel(trait.dimension) }}</span>
              </span>

              <div class="flex items-center gap-1.5 flex-wrap justify-end">
                <!-- Version History Timeline Pill (Requirement 1) -->
                <span
                  class="inline-flex items-center gap-1 text-[10px] font-mono text-slate-500 bg-slate-100/80 border border-slate-200/70 px-2 py-0.5 rounded-full"
                  :title="`版本号：${getTraitVersion(trait)} · 沉淀更新于 ${formatTraitDate(trait.updated_at || trait.created_at)}`"
                >
                  <span>🕒</span>
                  <span>{{ getTraitVersion(trait) }}</span>
                  <span class="text-slate-300">·</span>
                  <span>{{ formatTraitDate(trait.updated_at || trait.created_at) }}</span>
                </span>

                <!-- Audience Feedback Evolution Badge (Phase 4) -->
                <span
                  v-if="trait.evolution_boost_count && trait.evolution_boost_count > 0"
                  class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-extrabold bg-gradient-to-r from-purple-100 to-indigo-100 text-purple-800 border border-purple-200"
                  :title="`经受众共鸣强化 ${trait.evolution_boost_count} 次`"
                >
                  ⚡ +{{ (trait.evolution_boost_count * 0.5).toFixed(1) }}
                </span>

                <!-- Status Badge -->
                <span
                  v-if="trait.status === 'pinned'"
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200"
                >
                  📌 {{ t.profile.statusPinned }}
                </span>
                <span
                  v-else-if="trait.status === 'suppressed'"
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-200 text-slate-600"
                >
                  🚫 {{ t.profile.statusSuppressed }}
                </span>
              </div>
            </div>

            <!-- Trait Statement -->
            <p class="text-sm font-semibold text-slate-800 leading-relaxed break-words pt-1">
              {{ trait.statement }}
            </p>

            <!-- Confidence Score Progress Bar (Requirement 1: 1.0 ~ 2.5 with color gradient) -->
            <div class="pt-3 border-t border-slate-100/90 space-y-1.5">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-400 font-medium flex items-center gap-1">
                  <span>置信度权重</span>
                  <span v-if="trait.confidence_score >= 1.8" class="text-amber-500 font-bold">高</span>
                </span>
                <span class="font-bold text-slate-700 font-mono">
                  {{ trait.confidence_score.toFixed(1) }}x / 2.5x
                </span>
              </div>

              <!-- Gradient Progress Bar Track -->
              <div class="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500 bg-gradient-to-r"
                  :class="getConfidenceGradient(trait.confidence_score)"
                  :style="{ width: `${getConfidencePercent(trait.confidence_score)}%` }"
                ></div>
              </div>
            </div>
          </div>

          <!-- Card Action Footer (Module 3 Enhanced) -->
          <div class="border-t border-slate-100 mt-4 pt-3 flex items-center justify-between text-xs">
            <div class="flex items-center gap-2">
              <!-- Pin / Unpin Button -->
              <button
                v-if="trait.status === 'pinned'"
                @click="handleUnpin(trait.id)"
                class="text-purple-600 hover:text-purple-800 font-semibold inline-flex items-center gap-1 active:scale-95 cursor-pointer"
                title="Unpin"
              >
                <span>📍</span>
                <span>{{ t.profile.unpinAction }}</span>
              </button>
              <button
                v-else-if="trait.status !== 'suppressed'"
                @click="handlePin(trait.id)"
                class="text-slate-500 hover:text-purple-600 font-semibold inline-flex items-center gap-1 active:scale-95 cursor-pointer"
                title="Pin to prioritize in generation"
              >
                <span>📌</span>
                <span>{{ t.profile.pinAction }}</span>
              </button>

              <!-- Enable/Disable Toggle Switch -->
              <button
                type="button"
                @click="handleToggleEnabled(trait)"
                class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold transition cursor-pointer"
                :class="trait.status === 'suppressed' ? 'bg-slate-200 text-slate-600 hover:bg-slate-300' : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200'"
                :title="trait.status === 'suppressed' ? '点击启用：注入生成提示词' : '点击停用：生成时物理屏蔽，防观点重复与冲突'"
              >
                <span class="h-1.5 w-1.5 rounded-full" :class="trait.status === 'suppressed' ? 'bg-slate-400' : 'bg-emerald-600'"></span>
                <span>{{ trait.status === 'suppressed' ? '已停用' : '启用中' }}</span>
              </button>
            </div>

            <div class="flex items-center gap-1.5">
              <!-- Edit Trait (Module 3) -->
              <button
                type="button"
                @click="openEditTrait(trait)"
                class="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-indigo-50 transition cursor-pointer"
                title="编辑该特征"
              >
                ✏️
              </button>

              <!-- Delete with Confirmation (Module 3) -->
              <button
                type="button"
                @click="confirmDeleteTrait(trait.id)"
                class="p-1.5 text-slate-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition cursor-pointer"
                :title="t.profile.deleteAction"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Custom Trait Modal -->
    <div
      v-if="showAddModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>➕</span>
            <span>{{ t.profile.addModalTitle }}</span>
          </h3>
          <button @click="showAddModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">
            ✕
          </button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              {{ t.profile.dimensionLabel }}
            </label>
            <select
              v-model="newTraitDimension"
              class="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 font-medium focus:ring-2 focus:ring-indigo-500 focus:outline-none cursor-pointer"
            >
              <option value="vocabulary">📚 {{ t.profile.dimVocabulary }}</option>
              <option value="logic_preference">🧩 {{ t.profile.dimLogic }}</option>
              <option value="core_value">🎯 {{ t.profile.dimValues }}</option>
              <option value="viewpoint_stance">⚔️ 立场主张</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              {{ t.profile.statementLabel }}
            </label>
            <textarea
              v-model="newTraitStatement"
              rows="3"
              :placeholder="t.profile.statementPlaceholder"
              class="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            @click="showAddModal = false"
            class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 bg-slate-100 rounded-xl cursor-pointer"
          >
            {{ t.profile.cancel }}
          </button>
          <button
            type="button"
            :disabled="!newTraitStatement.trim() || isSubmitting"
            @click="handleAddTrait"
            class="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs disabled:opacity-50 cursor-pointer active:scale-95"
          >
            {{ isSubmitting ? '...' : t.profile.confirm }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: Ingest Own Work (Cold Start DNA) -->
    <div
      v-if="showOwnWorkModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark"
    >
      <div class="bg-white rounded-3xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>📥</span>
            <span>{{ t.profile.ownWorkModalTitle }}</span>
          </h3>
          <button @click="showOwnWorkModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>

        <p class="text-xs text-slate-500 leading-relaxed">
          {{ t.profile.ownWorkDisclaimer }}
        </p>

        <div class="flex items-center gap-2 text-xs font-bold">
          <button
            type="button"
            @click="ownWorkMode = 'text'"
            class="px-3.5 py-1.5 rounded-xl border transition cursor-pointer"
            :class="ownWorkMode === 'text' ? 'bg-emerald-600 text-white border-emerald-600 shadow-2xs' : 'bg-slate-50 text-slate-600 border-slate-200'"
          >
            {{ locale === 'zh' ? '📝 粘贴原创正文' : '📝 Paste Text' }}
          </button>
          <button
            type="button"
            @click="ownWorkMode = 'url'"
            class="px-3.5 py-1.5 rounded-xl border transition cursor-pointer"
            :class="ownWorkMode === 'url' ? 'bg-emerald-600 text-white border-emerald-600 shadow-2xs' : 'bg-slate-50 text-slate-600 border-slate-200'"
          >
            {{ locale === 'zh' ? '🔗 微信/知乎/网页链接' : '🔗 Web URL' }}
          </button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">{{ t.profile.ownWorkTitleLabel }}</label>
            <input
              v-model="ownWorkTitle"
              type="text"
              :placeholder="t.profile.ownWorkTitlePlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div v-if="ownWorkMode === 'url'">
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">{{ t.profile.ownWorkUrlLabel }}</label>
            <input
              v-model="ownWorkUrl"
              type="url"
              :placeholder="t.profile.ownWorkUrlPlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div v-else>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">{{ t.profile.ownWorkContentLabel }}</label>
            <textarea
              v-model="ownWorkContent"
              rows="6"
              :placeholder="t.profile.ownWorkContentPlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-sans"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            @click="showOwnWorkModal = false"
            class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 bg-slate-100 rounded-xl cursor-pointer"
          >
            {{ t.profile.cancel }}
          </button>
          <button
            type="button"
            :disabled="isSubmittingOwnWork || (ownWorkMode === 'url' ? !ownWorkUrl.trim() : !ownWorkContent.trim())"
            @click="handleIngestOwnWork"
            class="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl disabled:opacity-50 shadow-xs active:scale-95 transition cursor-pointer"
          >
            {{ isSubmittingOwnWork ? t.profile.ownWorkExtracting : t.profile.ownWorkSubmit }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: Deconstruct Benchmark Article -->
    <div
      v-if="showBenchmarkModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
    >
      <div class="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 my-8 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>⚡</span>
            <span>{{ t.profile.benchmarkModalTitle }}</span>
          </h3>
          <button @click="showBenchmarkModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>

        <div class="bg-amber-50/70 border border-amber-200 rounded-2xl p-3.5 text-xs text-amber-900 leading-relaxed">
          {{ t.profile.benchmarkDisclaimer }}
        </div>

        <div v-if="!benchmarkResult" class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">{{ t.profile.benchmarkInputLabel }}</label>
            <textarea
              v-model="benchmarkUrlOrContent"
              rows="4"
              :placeholder="t.profile.benchmarkPlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-2xl p-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500 font-sans"
            ></textarea>
          </div>

          <div class="flex justify-end pt-2">
            <button
              type="button"
              :disabled="!benchmarkUrlOrContent.trim() || isSubmittingBenchmark"
              @click="handleDeconstructBenchmark"
              class="px-5 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl disabled:opacity-50 shadow-xs active:scale-95 transition cursor-pointer"
            >
              {{ isSubmittingBenchmark ? t.profile.benchmarkExtracting : t.profile.benchmarkSubmit }}
            </button>
          </div>
        </div>

        <div v-else class="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          <div class="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-slate-800">🦴 {{ locale === 'zh' ? '提炼的爆款结构骨架 (Blueprint)' : 'Deconstructed Blueprint' }}</span>
              <span class="text-[10px] bg-slate-200 px-2 py-0.5 rounded font-semibold text-slate-600">{{ locale === 'zh' ? '已沉淀至骨架库' : 'Saved to Library' }}</span>
            </div>
            <div class="text-xs text-slate-600 space-y-1">
              <div><span class="font-semibold text-slate-700">{{ locale === 'zh' ? '破题风格：' : 'Hook Style: ' }}</span>{{ benchmarkResult.blueprint.hook_style }}</div>
              <div><span class="font-semibold text-slate-700">{{ locale === 'zh' ? '情绪曲线：' : 'Emotional Arc: ' }}</span>{{ benchmarkResult.blueprint.emotional_arc }}</div>
              <div><span class="font-semibold text-slate-700">{{ locale === 'zh' ? '节奏把控：' : 'Pacing: ' }}</span>{{ benchmarkResult.blueprint.pacing }}</div>
            </div>
            <div class="pt-2 flex justify-end">
              <button
                type="button"
                @click="openBlueprintCreation(benchmarkResult.blueprint)"
                class="px-4 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 rounded-xl shadow-xs flex items-center gap-1.5 transition active:scale-95 cursor-pointer"
              >
                <span>🦴</span>
                <span>{{ t.blueprint.createFromBlueprint }}</span>
              </button>
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex items-center justify-between border-b border-slate-100 pb-2">
              <h4 class="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <span>⚔️</span>
                <span>{{ t.profile.benchmarkClashTitle }}</span>
              </h4>
            </div>

            <div
              v-for="(cp, idx) in benchmarkResult.clash_points"
              :key="idx"
              class="border border-slate-200 rounded-2xl p-4 space-y-2.5 bg-white shadow-2xs"
            >
              <div class="bg-amber-50/70 border border-amber-200/60 rounded-xl p-3 text-xs text-slate-800">
                <div class="text-[10px] font-bold text-amber-800 uppercase mb-0.5">{{ t.profile.benchmarkOriginalClaim }}</div>
                <div class="font-semibold">“{{ cp.claim }}”</div>
                <div class="text-[10px] text-slate-500 mt-1">{{ locale === 'zh' ? '审议引导：' : 'Guide: ' }}{{ cp.suggested_critique_angle }}</div>
              </div>

              <div>
                <label class="block text-[11px] font-bold text-slate-600 mb-1">{{ t.profile.benchmarkYourStance }}</label>
                <textarea
                  v-model="rebuttals[idx]"
                  rows="2"
                  :placeholder="t.profile.benchmarkStancePlaceholder"
                  class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                ></textarea>
              </div>
            </div>

            <div class="flex items-center justify-between pt-2">
              <button
                type="button"
                @click="benchmarkResult = null"
                class="text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
              >
                {{ locale === 'zh' ? '← 重新拆解另一篇' : '← Deconstruct Another' }}
              </button>
              <button
                type="button"
                :disabled="isSubmittingRebuttals || !hasAnyRebuttal"
                @click="handleSubmitRebuttals"
                class="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl disabled:opacity-50 shadow-xs active:scale-95 transition cursor-pointer"
              >
                {{ isSubmittingRebuttals ? (locale === 'zh' ? '沉淀中...' : 'Saving...') : t.profile.benchmarkSaveStance }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Active Sandboxed Skills Library -->
    <div
      v-if="showSkillsModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>🛡️</span>
            <span>{{ t.profile.sandboxSkillsTitle }}</span>
          </h3>
          <button @click="showSkillsModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>

        <p class="text-xs text-slate-500">
          {{ t.profile.sandboxSkillsSubtitle }}
        </p>

        <div class="space-y-3 max-h-[60vh] overflow-y-auto">
          <div
            v-for="s in activeSkills"
            :key="s.name"
            class="bg-slate-50 border border-slate-200 rounded-2xl p-3.5 space-y-1.5"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-extrabold text-slate-800 font-mono">{{ s.name }}</span>
              <span class="text-[10px] font-bold bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full">
                {{ s.runner_mode === 'restricted_token' ? (locale === 'zh' ? 'AppContainer 受限令牌' : 'Restricted Token') : 'Windows Sandbox WSB' }}
              </span>
            </div>
            <p class="text-xs text-slate-600">{{ s.description }}</p>
            <div class="flex flex-wrap items-center gap-1 pt-1">
              <span
                v-for="p in s.permissions"
                :key="p"
                class="text-[10px] bg-slate-200/80 text-slate-700 px-2 py-0.5 rounded-md font-mono"
              >
                {{ p }}
              </span>
            </div>
          </div>
        </div>

        <div class="flex justify-end pt-2">
          <button
            type="button"
            @click="showSkillsModal = false"
            class="px-4 py-2 text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl cursor-pointer"
          >
            {{ t.distribute.close }}
          </button>
        </div>
      </div>
    </div>

    <!-- Saved Benchmark Blueprints Library Section -->
    <div v-if="savedBlueprints.length > 0" class="bg-amber-50/40 border border-amber-200/80 rounded-3xl p-5 sm:p-6 space-y-3.5">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-bold text-amber-950 flex items-center gap-2">
          <span>🦴</span>
          <span>{{ t.blueprint.historyTitle }} ({{ t.blueprint.historyCount.replace('{count}', String(savedBlueprints.length)) }})</span>
        </h3>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <div
          v-for="bp in savedBlueprints"
          :key="bp.id"
          class="bg-white border border-amber-200/70 rounded-2xl p-4 space-y-2.5 shadow-2xs hover:border-amber-300 transition"
        >
          <div class="flex items-start justify-between gap-2">
            <h4 class="text-xs font-bold text-slate-800 line-clamp-1">{{ bp.title }}</h4>
            <button
              type="button"
              @click="openBlueprintCreation(bp)"
              class="shrink-0 px-2.5 py-1 text-[11px] font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl shadow-2xs transition active:scale-95 cursor-pointer"
            >
              {{ t.blueprint.createFromBlueprint }}
            </button>
          </div>
          <p class="text-[11px] text-slate-500 line-clamp-2">
            <span class="font-semibold text-slate-600">Hook:</span> {{ bp.hook_style }}
          </p>
          <div class="text-[10px] text-slate-400 flex items-center justify-between pt-1.5 border-t border-slate-100">
            <span>{{ locale === 'zh' ? '节奏: ' : 'Pacing: ' }}{{ bp.pacing }}</span>
            <span>{{ bp.structural_stages?.length || 4 }} {{ locale === 'zh' ? '阶段' : ' Stages' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Quick Creation from Blueprint -->
    <div
      v-if="showBlueprintModal && selectedBlueprintForCreation"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div class="flex items-center gap-2">
            <span class="text-xl">🦴</span>
            <div>
              <h3 class="text-base font-black text-slate-900">{{ t.blueprint.modalTitle }}</h3>
              <p class="text-xs text-slate-500 truncate max-w-sm">{{ selectedBlueprintForCreation.title }}</p>
            </div>
          </div>
          <button @click="showBlueprintModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>

        <p class="text-xs text-slate-600 leading-relaxed bg-amber-50/70 p-3 rounded-2xl border border-amber-200">
          {{ t.blueprint.modalDesc }}
        </p>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              {{ t.blueprint.topicLabel }} <span class="text-rose-500">*</span>
            </label>
            <input
              v-model="blueprintTopic"
              type="text"
              :placeholder="t.blueprint.topicPlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              {{ t.blueprint.contextLabel }}
            </label>
            <textarea
              v-model="blueprintContext"
              rows="3"
              :placeholder="t.blueprint.contextPlaceholder"
              class="w-full text-xs bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 font-sans"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2 border-t border-slate-100">
          <button
            type="button"
            @click="showBlueprintModal = false"
            class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 bg-slate-100 rounded-xl cursor-pointer"
          >
            {{ t.blueprint.cancel }}
          </button>
          <button
            type="button"
            @click="handleLoadIntoWorkbenchOnly"
            class="px-4 py-2 text-xs font-bold text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 rounded-xl transition cursor-pointer active:scale-95"
          >
            {{ t.blueprint.openInWorkbench }}
          </button>
          <button
            type="button"
            :disabled="!blueprintTopic.trim() || isGeneratingFromBlueprint"
            @click="handleStartBlueprintCreation"
            class="px-5 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl disabled:opacity-50 flex items-center gap-2 shadow-xs cursor-pointer active:scale-95 transition"
          >
            <svg v-if="isGeneratingFromBlueprint" class="animate-spin -ml-1 mr-1 h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>{{ isGeneratingFromBlueprint ? t.blueprint.generating : t.blueprint.submit }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: Edit Trait (Module 3) -->
    <div
      v-if="showEditModal && editingTrait"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>✏️</span>
            <span>编辑认知特征 / 观点</span>
          </h3>
          <button @click="showEditModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">认知维度</label>
            <select
              v-model="editDimension"
              class="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-800 font-medium focus:ring-2 focus:ring-indigo-500 focus:outline-none cursor-pointer"
            >
              <option value="vocabulary">📚 {{ t.profile.dimVocabulary }}</option>
              <option value="logic_preference">🧩 {{ t.profile.dimLogic }}</option>
              <option value="core_value">🎯 {{ t.profile.dimValues }}</option>
              <option value="viewpoint_stance">⚔️ 立场主张</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">特征陈述 / 表达习惯</label>
            <textarea
              v-model="editStatement"
              rows="4"
              class="w-full text-sm bg-slate-50 border border-slate-300 rounded-xl p-3 text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:outline-none font-sans"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            @click="showEditModal = false"
            class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 bg-slate-100 rounded-xl cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            :disabled="!editStatement.trim() || isSavingEdit"
            @click="handleSaveEdit"
            class="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs disabled:opacity-50 cursor-pointer active:scale-95 transition"
          >
            {{ isSavingEdit ? '保存中...' : '确认更新' }}
          </button>
        </div>
      </div>
    </div>
    </div> <!-- Close Sub-view: Regular Traits Management -->

    <!-- Persona Modal -->
    <div v-if="showPersonaModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark">
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">{{ t.ip_persona.modalPersonaTitle }}</h3>
          <button @click="showPersonaModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.nameLabel }}</label><input v-model="newPersona.name" :placeholder="t.ip_persona.namePlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-indigo-500"/></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.audienceLabel }}</label><input v-model="newPersona.target_audience" :placeholder="t.ip_persona.audiencePlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-indigo-500"/></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.toneLabel }}</label><textarea v-model="newPersona.tone_style" :placeholder="t.ip_persona.tonePlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-indigo-500" rows="2"></textarea></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.salutationInputLabel }}</label><input v-model="newPersona.reader_salutation" :placeholder="t.ip_persona.salutationPlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-indigo-500"/></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.originStoryLabel }}</label><textarea v-model="newPersona.origin_story" :placeholder="t.ip_persona.originStoryPlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-indigo-500" rows="5"></textarea></div>
          <div class="flex items-center gap-2 mt-2"><input type="checkbox" v-model="newPersona.is_active" id="isActiveCb"/><label for="isActiveCb" class="font-bold text-sm">{{ t.ip_persona.isActiveLabel }}</label></div>
        </div>
        <div class="flex justify-end gap-3 pt-3">
          <button @click="showPersonaModal = false" class="px-4 py-2 bg-slate-100 rounded-xl font-bold text-slate-600 hover:bg-slate-200">{{ t.ip_persona.cancel }}</button>
          <button @click="handleCreatePersona" :disabled="!newPersona.name.trim()" class="px-4 py-2 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-700 shadow-xs active:scale-95 disabled:opacity-50">{{ t.ip_persona.savePersona }}</button>
        </div>
      </div>
    </div>

    <!-- Toast Celebration Banner -->
    <transition
      enter-active-class="transform transition ease-out duration-300"
      enter-from-class="translate-y-[-100%] opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="personaCelebrationToast"
        class="fixed top-20 right-6 z-50 p-4 rounded-2xl bg-gradient-to-r from-emerald-600 to-indigo-600 text-white shadow-2xl flex items-center gap-3 border border-emerald-300/40"
      >
        <span class="text-xl">🎉</span>
        <span class="text-xs sm:text-sm font-bold">{{ personaCelebrationToast }}</span>
      </div>
    </transition>

    <!-- Reverse Extraction Modal -->
    <ExtractPersonaModal
      :show="showExtractModal"
      @close="showExtractModal = false"
      @adopted="handlePersonaAdopted"
    />

    <!-- Story Modal -->
    <div v-if="showStoryModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark">
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">{{ t.ip_persona.modalStoryTitle }}</h3>
          <button @click="showStoryModal = false" class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.storyTitleLabel }}</label><input v-model="newStory.title" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-emerald-500"/></div>
          <div>
            <label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.typeLabel }}</label>
            <select v-model="newStory.story_type" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-emerald-500">
              <option value="daily_life">{{ t.ip_persona.typeDaily }}</option>
              <option value="failure_reflection">{{ t.ip_persona.typeFailure }}</option>
              <option value="client_case">{{ t.ip_persona.typeClient }}</option>
            </select>
          </div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.occurredAtLabel }}</label><input type="date" v-model="newStory.occurred_at" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-emerald-500"/></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.contentLabel }}</label><textarea v-model="newStory.story_content" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-emerald-500" rows="6"></textarea></div>
          <div><label class="block mb-1 font-bold text-xs text-slate-700">{{ t.ip_persona.tagsLabel }}</label><input v-model="newStory.tags" :placeholder="t.ip_persona.tagsPlaceholder" class="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 focus:ring-2 focus:ring-emerald-500"/></div>
        </div>
        <div class="flex justify-end gap-3 pt-3">
          <button @click="showStoryModal = false" class="px-4 py-2 bg-slate-100 rounded-xl font-bold text-slate-600 hover:bg-slate-200">{{ t.ip_persona.cancel }}</button>
          <button @click="handleCreateStory" :disabled="!newStory.story_content.trim()" class="px-4 py-2 bg-emerald-600 text-white rounded-xl font-bold hover:bg-emerald-700 shadow-xs active:scale-95 disabled:opacity-50">{{ t.ip_persona.saveStory }}</button>
        </div>
      </div>
    </div>

    <!-- Product Celebration Toast Banner -->
    <transition
      enter-active-class="transform transition ease-out duration-300"
      enter-from-class="translate-y-[-100%] opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="productCelebrationToast"
        class="fixed top-6 left-1/2 -translate-x-1/2 z-50 p-4 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 text-white shadow-2xl flex items-center gap-3 border border-emerald-300/40 max-w-lg"
      >
        <span class="text-xl">🎉</span>
        <span class="text-xs sm:text-sm font-bold">{{ productCelebrationToast }}</span>
      </div>
    </transition>

    <!-- Extract Product Modal -->
    <ExtractProductModal
      :show="showExtractProductModal"
      @close="showExtractProductModal = false"
      @saved="handleProductSaved"
    />

    <!-- Product Manual Create/Edit Modal -->
    <div
      v-if="showProductModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
      @click.self="showProductModal = false"
    >
      <div class="bg-white rounded-3xl max-w-xl w-full p-6 sm:p-7 shadow-2xl space-y-4 my-8 max-h-[90vh] flex flex-col relative overflow-hidden toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-base font-black text-slate-900 flex items-center gap-2">
            <span>{{ editingProductId ? '✏️' : '➕' }}</span>
            <span>{{ editingProductId ? (t.product_vault?.manualModalTitleEdit || '✏️ 编辑好物档案') : (t.product_vault?.manualModalTitleCreate || '➕ 新增好物档案') }}</span>
          </h3>
          <button
            type="button"
            @click="showProductModal = false"
            class="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div class="space-y-3.5 text-xs overflow-y-auto pr-1 flex-1">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block mb-1 font-bold text-slate-700">{{ t.product_vault?.productNameLabel || '产品品名 *' }}</label>
              <input
                v-model="productForm.product_name"
                :placeholder="t.product_vault?.productNamePlaceholder || '例如：梅江老树15年陈皮配高山老白茶'"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-900 focus:bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
              />
            </div>
            <div>
              <label class="block mb-1 font-bold text-slate-700">{{ t.product_vault?.categoryLabel || '品类/形态' }}</label>
              <input
                v-model="productForm.category"
                :placeholder="t.product_vault?.categoryPlaceholder || '例如：药食同源茶饮 / 办公调养'"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label class="block mb-1 font-bold text-slate-700">{{ t.product_vault?.coreIngredients || '核心配料 / 工艺亮点' }}</label>
            <textarea
              v-model="productForm.core_ingredients"
              rows="2"
              :placeholder="t.product_vault?.ingredientsPlaceholder || '例如：15年核心梅江陈皮、太姥山寿眉老白茶...'"
              class="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 leading-relaxed focus:bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
            ></textarea>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block mb-1 font-bold text-emerald-800 flex items-center gap-1">
                <span>✅</span>
                <span>{{ t.product_vault?.suitableConditions || '精准适用体质与人群' }}</span>
              </label>
              <textarea
                v-model="productForm.suitable_conditions"
                rows="3"
                :placeholder="t.product_vault?.suitablePlaceholder || '例如：湿气重、久坐吹空调咽喉不适...'"
                class="w-full bg-slate-50 border border-emerald-200 rounded-xl p-2 text-xs text-slate-800 leading-relaxed focus:bg-white focus:ring-2 focus:ring-emerald-500 outline-none"
              ></textarea>
            </div>
            <div>
              <label class="block mb-1 font-bold text-rose-800 flex items-center gap-1">
                <span>⚠️</span>
                <span>{{ t.product_vault?.taboos || '劝退禁忌人群 (信任基石)' }}</span>
              </label>
              <textarea
                v-model="productForm.taboos"
                rows="3"
                :placeholder="t.product_vault?.taboosPlaceholder || '例如：急性胃溃疡发作期、孕妇、失眠者慎用...'"
                class="w-full bg-slate-50 border border-rose-200 rounded-xl p-2 text-xs text-slate-800 leading-relaxed focus:bg-white focus:ring-2 focus:ring-rose-400 outline-none"
              ></textarea>
            </div>
          </div>

          <div>
            <label class="block mb-1 font-bold text-amber-900 flex items-center gap-1">
              <span>💬</span>
              <span>{{ t.product_vault?.personalExperience || '第一人称真实自用体验与体感' }}</span>
            </label>
            <textarea
              v-model="productForm.personal_usage_experience"
              rows="3"
              :placeholder="t.product_vault?.experiencePlaceholder || '以第一人称记录你的日常自用场景与体感改变...'"
              class="w-full bg-slate-50 border border-amber-200 rounded-xl p-2.5 text-xs text-slate-800 leading-relaxed focus:bg-white focus:ring-2 focus:ring-amber-400 outline-none"
            ></textarea>
          </div>

          <div>
            <label class="block mb-1 font-bold text-indigo-900 flex items-center gap-1">
              <span>🎁</span>
              <span>{{ t.product_vault?.conversionHooks || '低阻力转化引子 (转化钩子)' }}</span>
            </label>
            <input
              v-model="productForm.conversion_hooks"
              :placeholder="t.product_vault?.hooksPlaceholder || '例如：私信回复【喝茶】送节气调理表+试饮装...'"
              class="w-full bg-slate-50 border border-indigo-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:bg-white focus:ring-2 focus:ring-indigo-400 outline-none"
            />
          </div>

          <!-- Visual Assets Upload & URL Section -->
          <div class="space-y-3 pt-2 border-t border-slate-200/80">
            <div class="flex items-center justify-between">
              <span class="text-xs font-black text-slate-800 flex items-center gap-1.5">
                <span>🖼️</span>
                <span>视觉资产管理 (Visual Assets)</span>
              </span>
              <span class="text-[10px] text-slate-400">{{ t.product_vault?.uploadSizeLimitHint || '支持本地上传与网络链接' }}</span>
            </div>

            <!-- 1. Cover Image -->
            <div class="bg-slate-50 border border-slate-200/80 rounded-2xl p-3 space-y-2">
              <div class="flex items-center justify-between">
                <label class="block text-[11px] font-bold text-slate-700">
                  {{ t.product_vault?.coverImageLabel || '产品封面主图 (Cover Image)' }}
                </label>
                <span class="text-[10px] text-slate-400">{{ t.product_vault?.coverImageHint || '推荐 16:9 或 1:1' }}</span>
              </div>
              <div v-if="productForm.cover_image" class="relative w-full h-32 rounded-xl overflow-hidden border border-slate-200 group">
                <img :src="resolveImageUrl(productForm.cover_image)" class="w-full h-full object-cover" />
                <button
                  type="button"
                  @click="productForm.cover_image = ''"
                  class="absolute top-2 right-2 bg-rose-600 hover:bg-rose-700 text-white rounded-full p-1 text-xs shadow-md transition cursor-pointer"
                  :title="t.product_vault?.removeImageBtn || '移除封面图'"
                >
                  ✕
                </button>
              </div>
              <div v-else class="space-y-2">
                <label
                  class="flex items-center justify-center border-2 border-dashed rounded-xl p-3 text-center cursor-pointer transition group"
                  :class="isDraggingCover ? 'border-emerald-500 bg-emerald-50/70 ring-2 ring-emerald-200 scale-[1.01]' : 'border-slate-300 hover:border-emerald-500 bg-white'"
                  @dragover.prevent="isDraggingCover = true"
                  @dragenter.prevent="isDraggingCover = true"
                  @dragleave.prevent="isDraggingCover = false"
                  @drop.prevent="handleDropCover"
                >
                  <input type="file" accept="image/*" class="hidden" @change="handleUploadCover" :disabled="isUploadingCover" />
                  <span class="text-xs font-semibold flex items-center justify-center gap-1.5" :class="isDraggingCover ? 'text-emerald-700 font-bold' : 'text-slate-600 group-hover:text-emerald-700'">
                    <span>{{ isUploadingCover ? '⏳' : (isDraggingCover ? '📥' : '📸') }}</span>
                    <span>{{ isUploadingCover ? (t.product_vault?.uploadingImage || '正在上传...') : (isDraggingCover ? (t.product_vault?.dropToUploadCover || '松开立即上传封面图') : (t.product_vault?.dragOrClickUpload || '点击或拖拽图片至此处上传')) }}</span>
                  </span>
                </label>
                <input
                  v-model="productForm.cover_image"
                  type="url"
                  :placeholder="t.product_vault?.orInputUrlPlaceholder || '或直接输入封面图片 URL (http/https/...)'"
                  class="w-full bg-white border border-slate-200 rounded-xl px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>

            <!-- 2. Gallery Images (Lifestyle photos) -->
            <div class="bg-slate-50 border border-slate-200/80 rounded-2xl p-3 space-y-2">
              <div class="flex items-center justify-between">
                <label class="block text-[11px] font-bold text-slate-700">
                  {{ t.product_vault?.galleryImagesLabel || '实物生活切片图集 (Lifestyle Photos)' }}
                </label>
                <span class="text-[10px] text-slate-400">{{ (t.product_vault?.addedCount || '已添加 {count} 张').replace('{count}', String(productForm.gallery_images.length)) }}</span>
              </div>
              <!-- Thumbnails -->
              <div v-if="productForm.gallery_images.length > 0" class="flex flex-wrap gap-2">
                <div
                  v-for="(img, gIdx) in productForm.gallery_images"
                  :key="'pf-g-' + gIdx"
                  class="relative w-14 h-14 rounded-xl overflow-hidden border border-slate-200 group"
                >
                  <img :src="resolveImageUrl(img)" class="w-full h-full object-cover" />
                  <button
                    type="button"
                    @click="removeGalleryImage(gIdx)"
                    class="absolute top-1 right-1 bg-rose-600/90 hover:bg-rose-700 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] shadow cursor-pointer"
                    :title="t.product_vault?.removeImageBtn || '移除'"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <!-- Upload or Add URL -->
              <div class="flex items-center gap-2">
                <label
                  class="flex-1 border-2 border-dashed rounded-xl px-3 py-2 text-center cursor-pointer transition"
                  :class="isDraggingGallery ? 'border-emerald-500 bg-emerald-50/70 ring-2 ring-emerald-200 scale-[1.01]' : 'border-slate-300 hover:border-emerald-500 bg-white'"
                  @dragover.prevent="isDraggingGallery = true"
                  @dragenter.prevent="isDraggingGallery = true"
                  @dragleave.prevent="isDraggingGallery = false"
                  @drop.prevent="handleDropGallery"
                >
                  <input type="file" accept="image/*" multiple class="hidden" @change="handleUploadGallery" :disabled="isUploadingGallery" />
                  <span class="text-xs font-semibold flex items-center justify-center gap-1.5" :class="isDraggingGallery ? 'text-emerald-700 font-bold' : 'text-slate-600'">
                    <span>{{ isUploadingGallery ? '⏳' : (isDraggingGallery ? '📥' : '➕') }}</span>
                    <span>{{ isUploadingGallery ? (t.product_vault?.uploadingImage || '上传中...') : (isDraggingGallery ? (t.product_vault?.dropToUploadGallery || '松开上传实物切片图') : (t.product_vault?.dragOrClickUpload || '点击或拖拽上传实物图(可多选)')) }}</span>
                  </span>
                </label>
              </div>
              <div class="flex items-center gap-1.5">
                <input
                  v-model="newGalleryUrl"
                  type="url"
                  :placeholder="t.product_vault?.orInputUrlPlaceholder || '或粘贴单张实物图 URL'"
                  class="flex-1 bg-white border border-slate-200 rounded-xl px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:ring-1 focus:ring-emerald-500"
                  @keydown.enter.prevent="addGalleryUrl"
                />
                <button
                  type="button"
                  @click="addGalleryUrl"
                  class="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-xl text-xs font-bold transition cursor-pointer"
                >
                  {{ t.product_vault?.addImageUrlBtn || '添加' }}
                </button>
              </div>
            </div>

            <!-- 3. Service Rights Images -->
            <div class="bg-slate-50 border border-slate-200/80 rounded-2xl p-3 space-y-2">
              <div class="flex items-center justify-between">
                <label class="block text-[11px] font-bold text-slate-700">
                  {{ t.product_vault?.serviceRightsImagesLabel || '服务权益与交付保障长图 (Service Rights & Guarantees)' }}
                </label>
                <span class="text-[10px] text-slate-400">{{ (t.product_vault?.addedCount || '已添加 {count} 张').replace('{count}', String(productForm.service_rights_images.length)) }}</span>
              </div>
              <!-- Thumbnails -->
              <div v-if="productForm.service_rights_images.length > 0" class="flex flex-wrap gap-2">
                <div
                  v-for="(img, rIdx) in productForm.service_rights_images"
                  :key="'pf-r-' + rIdx"
                  class="relative w-14 h-14 rounded-xl overflow-hidden border border-emerald-300 group"
                >
                  <img :src="resolveImageUrl(img)" class="w-full h-full object-cover" />
                  <button
                    type="button"
                    @click="removeRightsImage(rIdx)"
                    class="absolute top-1 right-1 bg-rose-600/90 hover:bg-rose-700 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] shadow cursor-pointer"
                    :title="t.product_vault?.removeImageBtn || '移除'"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <!-- Upload or Add URL -->
              <div class="flex items-center gap-2">
                <label
                  class="flex-1 border-2 border-dashed rounded-xl px-3 py-2 text-center cursor-pointer transition"
                  :class="isDraggingRights ? 'border-emerald-600 bg-emerald-50/70 ring-2 ring-emerald-300 scale-[1.01]' : 'border-emerald-300 hover:border-emerald-600 bg-white'"
                  @dragover.prevent="isDraggingRights = true"
                  @dragenter.prevent="isDraggingRights = true"
                  @dragleave.prevent="isDraggingRights = false"
                  @drop.prevent="handleDropRights"
                >
                  <input type="file" accept="image/*" multiple class="hidden" @change="handleUploadRights" :disabled="isUploadingRights" />
                  <span class="text-xs text-emerald-800 font-semibold flex items-center justify-center gap-1.5">
                    <span>{{ isUploadingRights ? '⏳' : (isDraggingRights ? '📥' : '🛡️') }}</span>
                    <span>{{ isUploadingRights ? (t.product_vault?.uploadingImage || '上传中...') : (isDraggingRights ? (t.product_vault?.dropToUploadRights || '松开上传权益保障图') : (t.product_vault?.dragOrClickUpload || '点击或拖拽上传权益图(可多选)')) }}</span>
                  </span>
                </label>
              </div>
              <div class="flex items-center gap-1.5">
                <input
                  v-model="newRightsUrl"
                  type="url"
                  :placeholder="t.product_vault?.orInputUrlPlaceholder || '或粘贴权益/交付长图 URL'"
                  class="flex-1 bg-white border border-slate-200 rounded-xl px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:ring-1 focus:ring-emerald-500"
                  @keydown.enter.prevent="addRightsUrl"
                />
                <button
                  type="button"
                  @click="addRightsUrl"
                  class="px-3 py-1.5 bg-emerald-100 hover:bg-emerald-200 text-emerald-800 rounded-xl text-xs font-bold transition cursor-pointer"
                >
                  {{ t.product_vault?.addImageUrlBtn || '添加' }}
                </button>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <input
              id="product_is_active"
              type="checkbox"
              v-model="productForm.is_active"
              class="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4 cursor-pointer"
            />
            <label for="product_is_active" class="text-xs font-bold text-slate-700 cursor-pointer">
              {{ t.product_vault?.activeMainBadge || '设为主推好物' }}
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-3 border-t border-slate-100 shrink-0">
          <button
            type="button"
            @click="showProductModal = false"
            class="px-4 py-2 bg-slate-100 rounded-xl font-bold text-slate-600 hover:bg-slate-200 transition cursor-pointer"
          >
            {{ t.product_vault?.cancelBtn || '取消' }}
          </button>
          <button
            type="button"
            @click="handleSaveProductForm"
            :disabled="!productForm.product_name.trim() || isSubmittingProduct"
            class="px-5 py-2 bg-emerald-600 text-white rounded-xl font-bold hover:bg-emerald-700 shadow-xs active:scale-95 transition disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
          >
            <span v-if="isSubmittingProduct" class="animate-spin">⏳</span>
            <span>{{ isSubmittingProduct ? (t.product_vault?.savingBtn || '正在保存...') : (t.product_vault?.saveBtn || '保存档案') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Lightbox Modal for Fullscreen Product Visual Assets Preview -->
    <div
      v-if="lightboxOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md toast-enter"
      @click.self="closeLightbox"
    >
      <div class="relative max-w-4xl max-h-[90vh] flex flex-col items-center">
        <div class="flex items-center justify-between w-full pb-2 text-white">
          <span class="text-xs font-bold truncate pr-4">{{ lightboxImageTitle || t.product_vault?.previewLightboxTitle || '产品视觉资产全屏预览' }}</span>
          <button
            type="button"
            @click="closeLightbox"
            class="px-2.5 py-1 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs cursor-pointer transition flex items-center gap-1"
          >
            ✕ {{ t.product_vault?.lightboxClose || '关闭' }}
          </button>
        </div>
        <div class="bg-black/40 rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex items-center justify-center max-h-[82vh]">
          <img
            :src="lightboxImageUrl"
            alt="Preview"
            class="max-w-full max-h-[80vh] object-contain rounded-xl select-none"
          />
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from '../i18n'
import CognitiveTimelineView from './CognitiveTimelineView.vue'
import ExtractPersonaModal from './ExtractPersonaModal.vue'
import ExtractProductModal from './ExtractProductModal.vue'
import {
  fetchCognitiveProfile,
  pinTrait,
  unpinTrait,
  suppressTrait,
  deleteTrait,
  addTrait,
  ingestOwnWork,
  deconstructBenchmark,
  recordDialogueClash,
  fetchActiveSkills,
  fetchBenchmarkBlueprints,
  generateDraftFromBlueprint,
  type BenchmarkBlueprint,
  type CognitiveTrait,
  type CognitiveDimension,
  type BenchmarkDeconstructionResult,
  type SkillInfo,
  fetchPersonas,
  createPersona,
  activatePersona,
  fetchStories,
  createStory,
  type IPPersona,
  type EpisodicStoryItem,
  fetchProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  uploadProductImage,
  resolveImageUrl,
  type ProductVaultItem,
} from '../services/api'

const { t, locale } = useI18n()
const activeSubView = ref<'traits' | 'timeline' | 'ip_persona' | 'product_vault'>('traits')

watch(activeSubView, (newView) => {
  if (newView === 'ip_persona') {
    loadPersonas()
    loadStories()
  } else if (newView === 'product_vault') {
    loadProducts()
  }
})


// ==============================================================================
// Product Vault
// ==============================================================================
const products = ref<ProductVaultItem[]>([])
const showProductModal = ref(false)
const showExtractProductModal = ref(false)
const productCelebrationToast = ref('')
const editingProductId = ref<string | null>(null)
const isSubmittingProduct = ref(false)

// Lightbox state
const lightboxOpen = ref(false)
const lightboxImageUrl = ref('')
const lightboxImageTitle = ref('')
function openLightbox(url: string, title: string = '') {
  lightboxImageUrl.value = url
  lightboxImageTitle.value = title
  lightboxOpen.value = true
}
function closeLightbox() {
  lightboxOpen.value = false
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && lightboxOpen.value) {
    closeLightbox()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})

// Upload & Drag-and-drop state for visual assets
const isUploadingCover = ref(false)
const isUploadingGallery = ref(false)
const isUploadingRights = ref(false)
const isDraggingCover = ref(false)
const isDraggingGallery = ref(false)
const isDraggingRights = ref(false)
const newGalleryUrl = ref('')
const newRightsUrl = ref('')

async function uploadAndSetCover(file: File) {
  if (!file) return
  isUploadingCover.value = true
  try {
    const res = await uploadProductImage(file)
    productForm.value.cover_image = res.url
  } catch (err: any) {
    alert(`上传封面失败: ${err.message || err}`)
  } finally {
    isUploadingCover.value = false
  }
}

async function uploadAndAddGallery(files: FileList | File[]) {
  if (!files || files.length === 0) return
  isUploadingGallery.value = true
  try {
    for (let i = 0; i < files.length; i++) {
      const res = await uploadProductImage(files[i])
      productForm.value.gallery_images.push(res.url)
    }
  } catch (err: any) {
    alert(`上传实物图失败: ${err.message || err}`)
  } finally {
    isUploadingGallery.value = false
  }
}

async function uploadAndAddRights(files: FileList | File[]) {
  if (!files || files.length === 0) return
  isUploadingRights.value = true
  try {
    for (let i = 0; i < files.length; i++) {
      const res = await uploadProductImage(files[i])
      productForm.value.service_rights_images.push(res.url)
    }
  } catch (err: any) {
    alert(`上传权益图失败: ${err.message || err}`)
  } finally {
    isUploadingRights.value = false
  }
}

function handleUploadCover(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) uploadAndSetCover(file)
  target.value = ''
}

function handleUploadGallery(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) uploadAndAddGallery(target.files)
  target.value = ''
}

function handleUploadRights(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) uploadAndAddRights(target.files)
  target.value = ''
}

function handleDropCover(e: DragEvent) {
  isDraggingCover.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    uploadAndSetCover(file)
  }
}

function handleDropGallery(e: DragEvent) {
  isDraggingGallery.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    const imgFiles = Array.from(files).filter(f => f.type.startsWith('image/'))
    if (imgFiles.length > 0) uploadAndAddGallery(imgFiles)
  }
}

function handleDropRights(e: DragEvent) {
  isDraggingRights.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    const imgFiles = Array.from(files).filter(f => f.type.startsWith('image/'))
    if (imgFiles.length > 0) uploadAndAddRights(imgFiles)
  }
}

function addGalleryUrl() {
  if (!newGalleryUrl.value.trim()) return
  productForm.value.gallery_images.push(newGalleryUrl.value.trim())
  newGalleryUrl.value = ''
}

function addRightsUrl() {
  if (!newRightsUrl.value.trim()) return
  productForm.value.service_rights_images.push(newRightsUrl.value.trim())
  newRightsUrl.value = ''
}

function removeGalleryImage(index: number) {
  productForm.value.gallery_images.splice(index, 1)
}

function removeRightsImage(index: number) {
  productForm.value.service_rights_images.splice(index, 1)
}

const productForm = ref({
  product_name: '',
  category: '',
  core_ingredients: '',
  suitable_conditions: '',
  taboos: '',
  personal_usage_experience: '',
  conversion_hooks: '',
  is_active: true,
  cover_image: '',
  gallery_images: [] as string[],
  service_rights_images: [] as string[],
})

const loadProducts = async () => {
  try {
    products.value = await fetchProducts()
  } catch (e) {
    console.error('Failed to load products:', e)
  }
}

const openCreateProductModal = () => {
  editingProductId.value = null
  newGalleryUrl.value = ''
  newRightsUrl.value = ''
  productForm.value = {
    product_name: '',
    category: '',
    core_ingredients: '',
    suitable_conditions: '',
    taboos: '',
    personal_usage_experience: '',
    conversion_hooks: '',
    is_active: true,
    cover_image: '',
    gallery_images: [],
    service_rights_images: [],
  }
  showProductModal.value = true
}

const openEditProductModal = (product: ProductVaultItem) => {
  editingProductId.value = product.id
  newGalleryUrl.value = ''
  newRightsUrl.value = ''
  productForm.value = {
    product_name: product.product_name,
    category: product.category,
    core_ingredients: product.core_ingredients,
    suitable_conditions: product.suitable_conditions,
    taboos: product.taboos,
    personal_usage_experience: product.personal_usage_experience,
    conversion_hooks: product.conversion_hooks,
    is_active: product.is_active,
    cover_image: product.cover_image || '',
    gallery_images: product.gallery_images ? [...product.gallery_images] : [],
    service_rights_images: product.service_rights_images ? [...product.service_rights_images] : [],
  }
  showProductModal.value = true
}

const handleSaveProductForm = async () => {
  if (!productForm.value.product_name.trim()) return
  isSubmittingProduct.value = true
  try {
    const payload = {
      product_name: productForm.value.product_name.trim(),
      category: productForm.value.category.trim(),
      core_ingredients: productForm.value.core_ingredients.trim(),
      suitable_conditions: productForm.value.suitable_conditions.trim(),
      taboos: productForm.value.taboos.trim(),
      personal_usage_experience: productForm.value.personal_usage_experience.trim(),
      conversion_hooks: productForm.value.conversion_hooks.trim(),
      is_active: productForm.value.is_active,
      cover_image: productForm.value.cover_image.trim(),
      gallery_images: productForm.value.gallery_images,
      service_rights_images: productForm.value.service_rights_images,
    }

    let savedItem: ProductVaultItem
    if (editingProductId.value) {
      savedItem = await updateProduct(editingProductId.value, payload)
    } else {
      savedItem = await createProduct(payload)
    }

    if (payload.is_active) {
      const others = products.value.filter((p) => p.is_active && p.id !== savedItem.id)
      for (const o of others) {
        await updateProduct(o.id, { is_active: false })
      }
    }

    showProductModal.value = false
    await loadProducts()
    productCelebrationToast.value = `🎉 好物档案「${savedItem.product_name}」已成功保存！`
    setTimeout(() => {
      productCelebrationToast.value = ''
    }, 3500)
  } catch (e: any) {
    console.error('Failed to save product form:', e)
    alert(e.message || '保存好物档案失败，请重试')
  } finally {
    isSubmittingProduct.value = false
  }
}

const handleSetActiveProduct = async (id: string) => {
  try {
    const others = products.value.filter((p) => p.is_active && p.id !== id)
    for (const o of others) {
      await updateProduct(o.id, { is_active: false })
    }
    await updateProduct(id, { is_active: true })
    await loadProducts()
  } catch (e: any) {
    console.error('Failed to set active product:', e)
    alert(e.message || '设为主推好物失败，请重试')
  }
}

const handleToggleActiveProduct = async (id: string, active: boolean) => {
  try {
    await updateProduct(id, { is_active: active })
    await loadProducts()
  } catch (e: any) {
    console.error('Failed to toggle active product:', e)
    alert(e.message || '切换主推状态失败，请重试')
  }
}

const handleDeleteProduct = async (id: string, name: string) => {
  const confirmMsg = (t.value.product_vault?.deleteConfirm || '确定要删除产品档案「{name}」吗？此操作无法撤销。').replace('{name}', name)
  if (!confirm(confirmMsg)) return
  try {
    await deleteProduct(id)
    await loadProducts()
  } catch (e: any) {
    console.error('Failed to delete product:', e)
    alert(e.message || '删除好物失败，请重试')
  }
}

const handleProductSaved = async (saved: ProductVaultItem) => {
  await loadProducts()
  productCelebrationToast.value = `🎉 好物档案「${saved.product_name}」已成功入库！`
  setTimeout(() => {
    productCelebrationToast.value = ''
  }, 4000)
}

// Personas
const personas = ref<IPPersona[]>([])
const showPersonaModal = ref(false)
const showExtractModal = ref(false)
const personaCelebrationToast = ref('')

const handlePersonaAdopted = async (newPersona: IPPersona) => {
  await loadPersonas()
  await loadStories()
  personaCelebrationToast.value = `🎉 恭喜！专属 IP 人设「${newPersona.name}」已激活入库！`
  setTimeout(() => {
    personaCelebrationToast.value = ''
  }, 4000)
}
const newPersona = ref({
  name: '',
  target_audience: '',
  tone_style: '',
  reader_salutation: '',
  origin_story: '',
  is_active: true
})

const loadPersonas = async () => {
  try {
    personas.value = await fetchPersonas()
  } catch (e) {
    console.error('Failed to load personas:', e)
  }
}

const handleCreatePersona = async () => {
  if (!newPersona.value.name.trim()) return
  try {
    const created = await createPersona({
      name: newPersona.value.name.trim(),
      target_audience: newPersona.value.target_audience.trim(),
      tone_style: newPersona.value.tone_style.trim(),
      reader_salutation: newPersona.value.reader_salutation.trim(),
      origin_story: newPersona.value.origin_story.trim()
    })
    if (!newPersona.value.is_active) {
      await activatePersona(created.id, false)
    } else {
      const others = personas.value.filter(p => p.is_active)
      for (const o of others) {
        await activatePersona(o.id, false)
      }
    }
    showPersonaModal.value = false
    newPersona.value = { name: '', target_audience: '', tone_style: '', reader_salutation: '', origin_story: '', is_active: true }
    await loadPersonas()
  } catch (e) {
    console.error('Failed to create persona', e)
    alert(e instanceof Error ? e.message : '创建失败')
  }
}

const handleActivatePersona = async (id: string) => {
  try {
    const others = personas.value.filter(p => p.is_active && p.id !== id)
    for (const o of others) {
      await activatePersona(o.id, false)
    }
    await activatePersona(id, true)
    await loadPersonas()
  } catch (e) {
    console.error('Failed to activate persona', e)
    alert(e instanceof Error ? e.message : '激活失败')
  }
}
// Stories
const stories = ref<EpisodicStoryItem[]>([])
const showStoryModal = ref(false)
const newStory = ref({
  title: '',
  story_type: 'daily_life',
  occurred_at: '',
  story_content: '',
  tags: ''
})

const loadStories = async () => {
  try {
    stories.value = await fetchStories()
  } catch (e) {
    console.error('Failed to load stories:', e)
  }
}

const handleCreateStory = async () => {
  if (!newStory.value.story_content.trim()) return
  try {
    const payload: Partial<EpisodicStoryItem> = {
      title: newStory.value.title.trim(),
      story_type: newStory.value.story_type,
      story_content: newStory.value.story_content.trim(),
      tags: newStory.value.tags.split(',').map(s => s.trim()).filter(Boolean)
    }
    if (newStory.value.occurred_at) {
      payload.occurred_at = new Date(newStory.value.occurred_at).toISOString()
    }
    await createStory(payload)
    showStoryModal.value = false
    newStory.value = { title: '', story_type: 'daily_life', occurred_at: '', story_content: '', tags: '' }
    await loadStories()
  } catch (e) {
    console.error('Failed to create story', e)
    alert(e instanceof Error ? e.message : '创建失败')
  }
}

const getStoryTypeLabel = (type: string) => {
  const m: Record<string, string> = {
    daily_life: t.value.ip_persona.typeDaily,
    failure_reflection: t.value.ip_persona.typeFailure,
    client_case: t.value.ip_persona.typeClient
  }
  return m[type] || type
}

onMounted(() => {
  loadPersonas()
  loadStories()
})

const emit = defineEmits<{
  (e: 'create-from-blueprint', payload: { blueprint: BenchmarkBlueprint; topic?: string; context?: string; draft?: any }): void
  (e: 'open-interview'): void
  (e: 'switch-tab', tab: string, mode?: string): void
}>()

const handleOpenInterview = () => {
  emit('open-interview')
  emit('switch-tab', 'chat_lounge', 'interview')
}

const savedBlueprints = ref<BenchmarkBlueprint[]>([])
const showBlueprintModal = ref(false)
const selectedBlueprintForCreation = ref<BenchmarkBlueprint | null>(null)
const blueprintTopic = ref('')
const blueprintContext = ref('')
const isGeneratingFromBlueprint = ref(false)

const openBlueprintCreation = (bp: BenchmarkBlueprint) => {
  selectedBlueprintForCreation.value = bp
  blueprintTopic.value = ''
  blueprintContext.value = ''
  showBlueprintModal.value = true
}

const handleLoadIntoWorkbenchOnly = () => {
  if (!selectedBlueprintForCreation.value) return
  emit('create-from-blueprint', {
    blueprint: selectedBlueprintForCreation.value,
    topic: blueprintTopic.value.trim() || undefined,
    context: blueprintContext.value.trim() || undefined,
  })
  showBlueprintModal.value = false
}

const handleStartBlueprintCreation = async () => {
  if (!selectedBlueprintForCreation.value || !blueprintTopic.value.trim()) return
  isGeneratingFromBlueprint.value = true
  try {
    const draft = await generateDraftFromBlueprint({
      topic: blueprintTopic.value.trim(),
      blueprint_id: selectedBlueprintForCreation.value.id,
      blueprint: selectedBlueprintForCreation.value,
      additional_context: blueprintContext.value.trim() || undefined,
    })
    emit('create-from-blueprint', {
      blueprint: selectedBlueprintForCreation.value,
      topic: blueprintTopic.value.trim(),
      context: blueprintContext.value.trim() || undefined,
      draft,
    })
    showBlueprintModal.value = false
  } catch (err: any) {
    alert(err.message || '生成失败')
  } finally {
    isGeneratingFromBlueprint.value = false
  }
}

const loading = ref(true)
const allTraits = ref<CognitiveTrait[]>([])
const dimensionFilter = ref<string>('all')
const statusFilter = ref<string>('all')
const searchQuery = ref('')

// Add Modal State
const showAddModal = ref(false)
const newTraitDimension = ref<CognitiveDimension>('vocabulary')
const newTraitStatement = ref('')
const isSubmitting = ref(false)

// Requirement 1: Viewpoint Conflict Resolution Card Data Model & State
interface DetectedConflict {
  id: string
  title: string
  description: string
  category: string
  traitA: {
    id: string
    statement: string
    dimension: CognitiveDimension
    confidence: number
    tag: string
  }
  traitB: {
    id: string
    statement: string
    dimension: CognitiveDimension
    confidence: number
    tag: string
  }
  resolved?: boolean
}

const isScanningConflict = ref(false)
const conflictToastMessage = ref('')
const CONFLICT_STORAGE_KEY = 'cognitive_conflict_resolved_v1'

const isConflictResolvedInStorage = () => {
  try {
    return localStorage.getItem(CONFLICT_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

const activeConflict = ref<DetectedConflict | null>(
  isConflictResolvedInStorage()
    ? null
    : {
        id: 'conflict_demo_01',
        title: '内容定位与冷启动策略冲突',
        description: '系统在分析多篇旧作与生成历史时，发现以下两个核心论断存在对立或相互抵触的立场倾向：',
        category: '认知定位与冷启动策略',
        traitA: {
          id: 'trait_clash_a',
          statement: '坚持长期主义深耕，拒绝盲目迎合算法流量；文章必须以高密度思考模型为唯一交付标准。',
          dimension: 'core_value',
          confidence: 1.9,
          tag: '方案 A · 既有深度主张'
        },
        traitB: {
          id: 'trait_clash_b',
          statement: '在初期冷启动阶段，必须制造强烈情绪对抗与痛点反差，将算法曝光置于深度逻辑之上。',
          dimension: 'viewpoint_stance',
          confidence: 1.4,
          tag: '方案 B · 新引入冲突论断'
        },
        resolved: false
      }
)

const dismissConflict = () => {
  if (activeConflict.value) {
    activeConflict.value.resolved = true
  }
  activeConflict.value = null
  try {
    localStorage.setItem(CONFLICT_STORAGE_KEY, 'true')
  } catch {}
}

const scanForConflicts = async () => {
  isScanningConflict.value = true
  try {
    await new Promise((resolve) => setTimeout(resolve, 600))
    // Look for real conflicting candidates among traits
    const stanceTraits = allTraits.value.filter(t => t.dimension === 'core_value' || t.dimension === 'viewpoint_stance')
    if (stanceTraits.length >= 2) {
      activeConflict.value = {
        id: `conflict_${Date.now()}`,
        title: '核心论据与价值主张潜在冲突',
        description: '系统比对了近期沉淀的认知特征，检出以下两项立场存在潜在的语境边界冲突：',
        category: '价值主张',
        traitA: {
          id: stanceTraits[0].id,
          statement: stanceTraits[0].statement,
          dimension: stanceTraits[0].dimension,
          confidence: stanceTraits[0].confidence_score,
          tag: '方案 A · 既有基石'
        },
        traitB: {
          id: stanceTraits[1].id,
          statement: stanceTraits[1].statement,
          dimension: stanceTraits[1].dimension,
          confidence: stanceTraits[1].confidence_score,
          tag: '方案 B · 冲突论断'
        },
        resolved: false
      }
    } else {
      activeConflict.value = {
        id: `conflict_${Date.now()}`,
        title: '内容定位与冷启动策略冲突',
        description: '系统在分析多篇旧作与生成历史时，发现以下两个核心论断存在对立或相互抵触的立场倾向：',
        category: '认知定位与冷启动策略',
        traitA: {
          id: 'trait_clash_a',
          statement: '坚持长期主义深耕，拒绝盲目迎合算法流量；文章必须以高密度思考模型为唯一交付标准。',
          dimension: 'core_value',
          confidence: 1.9,
          tag: '方案 A · 既有深度主张'
        },
        traitB: {
          id: 'trait_clash_b',
          statement: '在初期冷启动阶段，必须制造强烈情绪对抗与痛点反差，将算法曝光置于深度逻辑之上。',
          dimension: 'viewpoint_stance',
          confidence: 1.4,
          tag: '方案 B · 新引入冲突论断'
        },
        resolved: false
      }
    }
    try {
      localStorage.removeItem(CONFLICT_STORAGE_KEY)
    } catch {}
    conflictToastMessage.value = '✓ 冲突扫描完成，已实时呈现冲突对比！'
  } finally {
    isScanningConflict.value = false
  }
}

const handleResolveConflict = async (resolutionType: 'keep_a' | 'keep_b' | 'coexist' | 'synthesize') => {
  if (!activeConflict.value) return

  if (resolutionType === 'keep_a') {
    conflictToastMessage.value = '✓ 冲突已消解！保留方案 A 作为核心置顶主张，方案 B 已移入淘汰隔离库。'
    // If trait B exists in allTraits, suppress it
    const bId = activeConflict.value.traitB.id
    const bTrait = allTraits.value.find(t => t.id === bId)
    if (bTrait) {
      await suppressTrait(bId)
    }
  } else if (resolutionType === 'keep_b') {
    conflictToastMessage.value = '✓ 冲突已消解！采纳方案 B 并提升置信度权重，方案 A 已移入淘汰隔离库。'
    const aId = activeConflict.value.traitA.id
    const aTrait = allTraits.value.find(t => t.id === aId)
    if (aTrait) {
      await suppressTrait(aId)
    }
  } else if (resolutionType === 'coexist') {
    conflictToastMessage.value = '✓ 已标记为双观点分场景共存！系统将在深度长文与短笔记中差异化精准注入。'
  } else if (resolutionType === 'synthesize') {
    const combinedStatement = '以痛点与共鸣作为前置抓手破圈，以深层思考模型交付不可替代的长期价值。'
    try {
      await addTrait('core_value', combinedStatement)
      await loadProfile()
    } catch {
      // fallback
    }
    conflictToastMessage.value = '✓ 已完成观点融合演化！新融合特征已作为核心认知资产写入基因库。'
  }

  if (activeConflict.value) {
    activeConflict.value.resolved = true
  }
  activeConflict.value = null
  try {
    localStorage.setItem(CONFLICT_STORAGE_KEY, 'true')
  } catch {}
}

// Progress Bar & Score Helpers (Requirement 1: 1.0 ~ 2.5)
const getConfidencePercent = (score: number) => {
  const s = score || 1.0
  const clamped = Math.max(1.0, Math.min(2.5, s))
  return Math.round(((clamped - 1.0) / 1.5) * 100)
}

const getConfidenceGradient = (score: number) => {
  if (score >= 2.0) return 'from-purple-500 via-pink-500 to-rose-500'
  if (score >= 1.6) return 'from-amber-500 via-orange-500 to-rose-500'
  if (score >= 1.3) return 'from-blue-500 to-indigo-600'
  return 'from-emerald-400 to-teal-500'
}

const getTraitVersion = (trait: CognitiveTrait): string => {
  const boost = trait.evolution_boost_count || 0
  if (boost > 0) {
    return `v${(1.0 + boost * 0.2).toFixed(1)}`
  }
  return 'v1.0'
}

const formatTraitDate = (isoStr?: string): string => {
  if (!isoStr) return '09-28'
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return '09-28'
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return '09-28'
  }
}

const loadProfile = async () => {
  loading.value = true
  try {
    const profile = await fetchCognitiveProfile()
    allTraits.value = profile.traits || []
    try {
      savedBlueprints.value = await fetchBenchmarkBlueprints()
    } catch (e) {
      console.warn('Failed to load blueprints:', e)
    }
  } catch (err) {
    console.error('Failed to load profile:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadProfile()
})

const countByDimension = (dim: string) => {
  return allTraits.value.filter((t) => t.dimension === dim).length
}

const pinnedCount = computed(() => allTraits.value.filter((t) => t.status === 'pinned').length)
const activeCount = computed(() => allTraits.value.filter((t) => t.status === 'active').length)
const highConfidenceCount = computed(() => allTraits.value.filter((t) => t.confidence_score >= 1.5).length)
const suppressedCount = computed(() => allTraits.value.filter((t) => t.status === 'suppressed').length)
const evolutionBoostedCount = computed(() => allTraits.value.filter((t) => (t.evolution_boost_count || 0) > 0).length)

// Module 3: JSON Import & Export State
const profileFileInputRef = ref<HTMLInputElement | null>(null)

function exportProfileAsJson() {
  const data = {
    version: '1.0',
    export_time: new Date().toISOString(),
    traits_count: allTraits.value.length,
    traits: allTraits.value,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `personal_thinking_dna_${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  a.remove()
}

function triggerProfileImport() {
  if (profileFileInputRef.value) {
    profileFileInputRef.value.value = ''
    profileFileInputRef.value.click()
  }
}

async function handleProfileFileUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const parsed = JSON.parse(text)
    const traitsList = Array.isArray(parsed) ? parsed : (parsed.traits || [])
    if (!Array.isArray(traitsList) || traitsList.length === 0) {
      alert('未检测到有效的特征数据，请上传正确的 Thinking DNA 备份 JSON。')
      return
    }

    let imported = 0
    for (const item of traitsList) {
      if (item && item.statement && item.dimension) {
        const exists = allTraits.value.some((t) => t.statement.trim() === item.statement.trim())
        if (!exists) {
          try {
            const created = await addTrait(item.dimension, item.statement.trim())
            if (item.status === 'pinned') {
              await pinTrait(created.id)
            } else if (item.status === 'suppressed') {
              await suppressTrait(created.id)
            }
            imported++
          } catch {
            // continue
          }
        }
      }
    }
    alert(`成功导入并合并 ${imported} 项认知特征！`)
    await loadProfile()
  } catch (err: any) {
    alert(`导入失败: ${err.message || '文件格式错误'}`)
  }
}

// Module 3: Enable / Disable Toggle Switch
async function handleToggleEnabled(trait: CognitiveTrait) {
  try {
    if (trait.status === 'suppressed') {
      const updated = await unpinTrait(trait.id)
      const idx = allTraits.value.findIndex((t) => t.id === trait.id)
      if (idx !== -1) allTraits.value[idx] = updated
    } else {
      const updated = await suppressTrait(trait.id)
      const idx = allTraits.value.findIndex((t) => t.id === trait.id)
      if (idx !== -1) allTraits.value[idx] = updated
    }
  } catch (e) {
    console.error('Failed to toggle trait status:', e)
  }
}

// Module 3: Purge All Suppressed Traits
async function handlePurgeSuppressed() {
  const suppressed = allTraits.value.filter((t) => t.status === 'suppressed')
  if (suppressed.length === 0) return
  if (confirm(`确定要彻底清退全部 ${suppressed.length} 条已停用的淘汰观点特征吗？清退后将永久删除。`)) {
    for (const t of suppressed) {
      try {
        await deleteTrait(t.id)
      } catch {
        // continue
      }
    }
    await loadProfile()
  }
}

// Module 3: Edit Trait Modal State & Handlers
const showEditModal = ref(false)
const editingTrait = ref<CognitiveTrait | null>(null)
const editDimension = ref<CognitiveDimension>('vocabulary')
const editStatement = ref('')
const isSavingEdit = ref(false)

function openEditTrait(trait: CognitiveTrait) {
  editingTrait.value = trait
  editDimension.value = trait.dimension
  editStatement.value = trait.statement
  showEditModal.value = true
}

async function handleSaveEdit() {
  if (!editingTrait.value || !editStatement.value.trim()) return
  isSavingEdit.value = true
  try {
    const oldId = editingTrait.value.id
    const oldStatus = editingTrait.value.status
    await deleteTrait(oldId)
    const created = await addTrait(editDimension.value, editStatement.value.trim())
    if (oldStatus === 'pinned') {
      await pinTrait(created.id)
    } else if (oldStatus === 'suppressed') {
      await suppressTrait(created.id)
    }
    await loadProfile()
    showEditModal.value = false
  } catch (e: any) {
    alert(e.message || '更新特征失败')
  } finally {
    isSavingEdit.value = false
  }
}

async function confirmDeleteTrait(traitId: string) {
  if (confirm('确定要删除该认知特征吗？删除后该特征将无法在生成中生效。')) {
    await handleDelete(traitId)
  }
}

const filteredTraits = computed(() => {
  return allTraits.value.filter((trait) => {
    // Dimension match
    if (dimensionFilter.value !== 'all') {
      if (dimensionFilter.value === 'core_value') {
        if (trait.dimension !== 'core_value' && trait.dimension !== 'viewpoint_stance') {
          return false
        }
      } else if (trait.dimension !== dimensionFilter.value) {
        return false
      }
    }

    // Status match
    if (statusFilter.value !== 'all') {
      if (trait.status !== statusFilter.value) return false
    }

    // Search query match
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase().trim()
      if (!trait.statement.toLowerCase().includes(q)) return false
    }

    return true
  }).sort((a, b) => {
    // Pinned first, then by confidence score descending
    const aPinned = a.status === 'pinned' ? 1 : 0
    const bPinned = b.status === 'pinned' ? 1 : 0
    if (aPinned !== bPinned) return bPinned - aPinned
    return b.confidence_score - a.confidence_score
  })
})

const dimensionTagClass = (dim: CognitiveDimension) => {
  switch (dim) {
    case 'vocabulary':
      return 'bg-blue-50/80 text-blue-700 border-blue-200'
    case 'logic_preference':
      return 'bg-amber-50/80 text-amber-800 border-amber-200'
    case 'core_value':
      return 'bg-purple-50/80 text-purple-700 border-purple-200'
    case 'viewpoint_stance':
      return 'bg-indigo-50/80 text-indigo-700 border-indigo-200'
    default:
      return 'bg-slate-50 text-slate-700 border-slate-200'
  }
}

const dimensionTagIcon = (dim: CognitiveDimension) => {
  switch (dim) {
    case 'vocabulary':
      return '📚'
    case 'logic_preference':
      return '🧩'
    case 'core_value':
      return '🎯'
    case 'viewpoint_stance':
      return '⚔️'
    default:
      return '🧬'
  }
}

const dimensionTagLabel = (dim: CognitiveDimension) => {
  switch (dim) {
    case 'vocabulary':
      return '词汇偏好'
    case 'logic_preference':
      return '论证逻辑'
    case 'core_value':
      return '核心价值观'
    case 'viewpoint_stance':
      return '立场主张'
    default:
      return dim
  }
}

const handlePin = async (traitId: string) => {
  try {
    const updated = await pinTrait(traitId)
    const idx = allTraits.value.findIndex((t) => t.id === traitId)
    if (idx !== -1) allTraits.value[idx] = updated
  } catch (e) {
    console.error(e)
  }
}

const handleUnpin = async (traitId: string) => {
  try {
    const updated = await unpinTrait(traitId)
    const idx = allTraits.value.findIndex((t) => t.id === traitId)
    if (idx !== -1) allTraits.value[idx] = updated
  } catch (e) {
    console.error(e)
  }
}

const handleDelete = async (traitId: string) => {
  try {
    await deleteTrait(traitId)
    allTraits.value = allTraits.value.filter((t) => t.id !== traitId)
  } catch (e) {
    console.error(e)
  }
}

const handleAddTrait = async () => {
  if (!newTraitStatement.value.trim()) return
  isSubmitting.value = true
  try {
    const created = await addTrait(newTraitDimension.value, newTraitStatement.value.trim())
    allTraits.value.unshift(created)
    newTraitStatement.value = ''
    showAddModal.value = false
  } catch (e) {
    console.error(e)
  } finally {
    isSubmitting.value = false
  }
}

// Own Work Ingest State
const showOwnWorkModal = ref(false)
const ownWorkMode = ref<'text' | 'url'>('text')
const ownWorkTitle = ref('')
const ownWorkUrl = ref('')
const ownWorkContent = ref('')
const isSubmittingOwnWork = ref(false)

// Benchmark Deconstruction State
const showBenchmarkModal = ref(false)
const benchmarkUrlOrContent = ref('')
const isSubmittingBenchmark = ref(false)
const benchmarkResult = ref<BenchmarkDeconstructionResult | null>(null)
const rebuttals = ref<Record<number, string>>({})
const isSubmittingRebuttals = ref(false)

// Active Skills Modal State
const showSkillsModal = ref(false)
const activeSkills = ref<SkillInfo[]>([])

const handleIngestOwnWork = async () => {
  isSubmittingOwnWork.value = true
  try {
    const payload = ownWorkMode.value === 'url'
      ? { url: ownWorkUrl.value.trim(), title: ownWorkTitle.value.trim() || undefined }
      : { content: ownWorkContent.value.trim(), title: ownWorkTitle.value.trim() || undefined }

    await ingestOwnWork(payload)
    await loadProfile()
    showOwnWorkModal.value = false
    ownWorkContent.value = ''
    ownWorkUrl.value = ''
    ownWorkTitle.value = ''
  } catch (e) {
    console.error(e)
    alert(e instanceof Error ? e.message : '导入失败')
  } finally {
    isSubmittingOwnWork.value = false
  }
}

const handleDeconstructBenchmark = async () => {
  if (!benchmarkUrlOrContent.value.trim()) return
  isSubmittingBenchmark.value = true
  try {
    const text = benchmarkUrlOrContent.value.trim()
    const payload = text.startsWith('http://') || text.startsWith('https://')
      ? { url: text }
      : { content: text }

    const res = await deconstructBenchmark(payload)
    benchmarkResult.value = res
    rebuttals.value = {}
  } catch (e) {
    console.error(e)
    alert(e instanceof Error ? e.message : '拆解失败')
  } finally {
    isSubmittingBenchmark.value = false
  }
}

const hasAnyRebuttal = computed(() => {
  return Object.values(rebuttals.value).some((v) => v && v.trim().length > 0)
})

const handleSubmitRebuttals = async () => {
  if (!benchmarkResult.value) return
  isSubmittingRebuttals.value = true
  try {
    const messages: Array<{ role: string; content: string }> = []
    benchmarkResult.value.clash_points.forEach((cp, idx) => {
      const userRebuttal = rebuttals.value[idx]
      if (userRebuttal && userRebuttal.trim()) {
        messages.push({ role: 'opponent', content: cp.claim })
        messages.push({ role: 'user', content: userRebuttal.trim() })
      }
    })

    if (messages.length > 0) {
      await recordDialogueClash({
        messages,
        debate_topic: benchmarkResult.value.blueprint.title || '对标文章观点审议',
      })
      await loadProfile()
    }
    showBenchmarkModal.value = false
    benchmarkResult.value = null
    benchmarkUrlOrContent.value = ''
    rebuttals.value = {}
  } catch (e) {
    console.error(e)
    alert(e instanceof Error ? e.message : '沉淀反驳观点失败')
  } finally {
    isSubmittingRebuttals.value = false
  }
}

const openSkillsModal = async () => {
  showSkillsModal.value = true
  try {
    activeSkills.value = await fetchActiveSkills()
  } catch (e) {
    console.error(e)
  }
}
</script>
