<template>
  <div class="space-y-8 max-w-7xl mx-auto">
    <!-- Header Banner -->
    <div class="glass-card rounded-3xl p-6 sm:p-8 shadow-sm relative overflow-hidden scroll-reveal">
      <!-- Multi-layer ambient glow blobs -->
      <div class="absolute -top-16 -right-16 w-80 h-80 bg-gradient-to-br from-emerald-200/50 via-teal-100/30 to-transparent rounded-full blur-3xl pointer-events-none"></div>
      <div class="absolute -bottom-8 -left-8 w-48 h-48 bg-gradient-to-tr from-indigo-100/40 via-sky-100/20 to-transparent rounded-full blur-2xl pointer-events-none"></div>
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
        <div>
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50/80 text-emerald-800 border border-emerald-200/60 mb-2 backdrop-blur-xs">
            <span>📱</span>
            <span>私域操盘中枢 · 微信朋友圈 5 维内容矩阵</span>
          </div>
          <h2 class="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight flex items-center gap-2.5">
            <span>私域 IP 操盘中枢</span>
            <span class="text-xs font-normal text-slate-400 bg-slate-100/80 px-2 py-0.5 rounded-md">V2.0 全息记忆融合</span>
          </h2>
          <p class="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
            三位一体锁合「Thinking DNA 认知底色 + IP 人设嘴巴 + 产品库自用体验」。前 6 行精准防折叠悬念，评论区一键置顶截流，自动生成 1:1 美学方图。
          </p>
        </div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            @click="activeSubMode = activeSubMode === 'community' ? 'moments' : 'community'"
            class="px-4 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer flex items-center gap-1.5 shadow-sm active:scale-95"
            :class="activeSubMode === 'community' ? 'bg-indigo-600 text-white border-indigo-600 shadow-indigo-500/20' : 'bg-white/80 text-slate-700 border-slate-200/80 hover:bg-slate-50'"
          >
            <span>💬</span>
            <span>{{ activeSubMode === 'community' ? '切换为朋友圈生成器' : '社群发售剧场 / 破冰' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- MAIN 3-COLUMN WORKSPACE -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- =================================================================== -->
      <!-- LEFT CONFIGURATION BAR (4 Cols) -->
      <!-- =================================================================== -->
      <div class="lg:col-span-4 space-y-5">
        <!-- 1. Persona Selector Card -->
        <div class="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4 scroll-reveal">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>👤</span>
              <span>IP 人设中枢 (Persona)</span>
            </h3>
            <span class="text-[11px] text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full font-semibold">
              决定读者称谓与语气
            </span>
          </div>

          <!-- Quick Persona Presets -->
          <div class="space-y-2">
            <div
              v-for="p in personas"
              :key="p.id"
              @click="selectedPersonaId = p.id"
              class="p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1 text-left relative"
              :class="
                selectedPersonaId === p.id
                  ? 'border-indigo-600 bg-indigo-50/50 shadow-2xs ring-1 ring-indigo-500/20'
                  : 'border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50'
              "
            >
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-900">{{ p.name }}</span>
                <span class="text-[10px] text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200">
                  称谓:「{{ p.reader_salutation || '姐妹们' }}」
                </span>
              </div>
              <p class="text-[11px] text-slate-500 line-clamp-1">
                {{ p.tone_style || '温暖专业接地气' }}
              </p>
            </div>
          </div>
        </div>

        <!-- 2. Product Vault Selector Card -->
        <div class="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>📦</span>
              <span>挂载产品自用档案 (Product Vault)</span>
            </h3>
            <span class="text-[10px] text-slate-400">可选植入</span>
          </div>

          <div class="space-y-2">
            <div
              @click="handleSelectProduct(null)"
              class="p-2.5 rounded-xl border text-xs font-semibold cursor-pointer transition text-left"
              :class="!selectedProductId ? 'border-slate-800 bg-slate-900 text-white' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
            >
              🍃 不挂载特定产品 (纯观点/生活日常)
            </div>
            <div
              v-for="prod in products"
              :key="prod.id"
              @click="handleSelectProduct(prod)"
              class="p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1 text-left"
              :class="
                selectedProductId === prod.id
                  ? 'border-emerald-600 bg-emerald-50/50 shadow-2xs ring-1 ring-emerald-500/20'
                  : 'border-slate-200/70 hover:border-slate-300 hover:bg-slate-50/50'
              "
            >
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-900">{{ prod.product_name }}</span>
                <span class="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                  {{ prod.category || '自用好物' }}
                </span>
              </div>
              <p class="text-[11px] text-slate-500 line-clamp-1">
                适用: {{ prod.suitable_conditions || '体虚调理' }}
              </p>
            </div>
          </div>
        </div>

        <!-- 3. Dimension Tabs & Time Mode -->
        <div class="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4">
          <div class="border-b border-slate-100 pb-3">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>🎛️</span>
              <span>朋友圈 5 维人设矩阵</span>
            </h3>
          </div>

          <!-- 5 Tabs -->
          <div class="grid grid-cols-1 gap-1.5">
            <button
              v-for="cat in momentCategories"
              :key="cat.id"
              type="button"
              @click="handleSelectCategory(cat.id)"
              class="w-full text-left px-3 py-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer flex items-center justify-between"
              :class="
                selectedCategory === cat.id
                  ? 'border-indigo-600 bg-indigo-600 text-white shadow-xs scale-[1.01]'
                  : 'border-slate-200 text-slate-700 hover:bg-slate-50'
              "
            >
              <span class="flex items-center gap-2">
                <span>{{ cat.icon }}</span>
                <span>{{ cat.title }}</span>
              </span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded-md"
                :class="selectedCategory === cat.id ? 'bg-indigo-700/80 text-white' : 'bg-slate-100 text-slate-500'"
              >
                {{ cat.tagline }}
              </span>
            </button>
          </div>

          <!-- Time Narrative Mode -->
          <div class="pt-3 border-t border-slate-100 space-y-2">
            <label class="text-xs font-bold text-slate-700 flex items-center justify-between">
              <span>⏱️ 时间叙事修辞转换器</span>
              <span class="text-[10px] text-slate-400">洗掉机械年月日</span>
            </label>
            <div class="grid grid-cols-2 gap-1.5 text-xs font-semibold">
              <button
                v-for="tm in timeModes"
                :key="tm.id"
                type="button"
                @click="timeNarrativeMode = tm.id"
                class="px-2.5 py-2 rounded-xl border transition-all cursor-pointer text-left text-[11px]"
                :class="
                  timeNarrativeMode === tm.id
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-800 font-bold shadow-2xs'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                "
              >
                {{ tm.label }}
              </button>
            </div>
          </div>

          <!-- 4. Trigger Source & Two-Layer Input Card -->
          <div class="pt-3 border-t border-slate-100 space-y-3">
            <div class="space-y-1.5">
              <label class="text-xs font-bold text-slate-700 flex items-center justify-between">
                <span>{{ t.moments_triggers?.sourceLabel || '触发源与切片类型' }}</span>
                <span class="text-[10px] text-slate-400">{{ t.moments_triggers?.sourceHint || '研习/古籍/案例' }}</span>
              </label>
              <!-- 4 Trigger Source Pills -->
              <div class="grid grid-cols-2 gap-1.5">
                <button
                  v-for="trig in triggerTypes"
                  :key="trig.id"
                  type="button"
                  @click="triggerType = trig.id"
                  class="px-2 py-1.5 rounded-xl border text-[11px] font-bold transition-all cursor-pointer text-left flex items-center gap-1.5"
                  :class="
                    triggerType === trig.id
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-800 shadow-2xs font-extrabold ring-1 ring-emerald-500/20'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  "
                >
                  <span>{{ trig.icon }}</span>
                  <span class="truncate">{{ trig.label }}</span>
                </button>
              </div>
            </div>

            <!-- Layer 1: Raw Experience / Learned Concept / Story -->
            <div>
              <label class="block text-xs font-bold text-slate-700 mb-1 flex items-center justify-between">
                <span>{{ t.moments_triggers?.rawExperienceLabel || '触发事件 / 所学知识 / 案例经历' }}</span>
                <span class="text-[10px] text-emerald-600 font-normal">第一现场切片</span>
              </label>
              <textarea
                v-model="rawExperience"
                rows="3"
                :placeholder="currentTriggerPlaceholder"
                class="w-full text-xs px-3 py-2 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none transition resize-none leading-relaxed"
              ></textarea>
            </div>

            <!-- Layer 2: Creator's Personal Takeaway & Attitude -->
            <div>
              <label class="block text-xs font-bold text-slate-700 mb-1 flex items-center justify-between">
                <span>{{ t.moments_triggers?.myTakeawayLabel || '我的个人感悟 / 态度立场 / 观点升华' }}</span>
                <span class="text-[10px] text-indigo-600 font-normal">认知 DNA 注入</span>
              </label>
              <textarea
                v-model="myTakeaway"
                rows="2"
                :placeholder="t.moments_triggers?.myTakeawayPlaceholder || '输入你的真实感悟或态度立场，AI 将以此为核心认知底色升华朋友圈...'"
                class="w-full text-xs px-3 py-2 rounded-xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none transition resize-none leading-relaxed"
              ></textarea>
            </div>

            <!-- 5. Length Tier & Fold Point Control -->
            <div class="space-y-1.5 pt-2 border-t border-slate-100">
              <label class="text-xs font-bold text-slate-700 flex items-center justify-between">
                <span>{{ t.moments_triggers?.lengthTierLabel || '篇幅与排版控折档位' }}</span>
                <span class="text-[10px] text-slate-400">{{ t.moments_triggers?.lengthTierHint || '把控折叠阈值' }}</span>
              </label>
              <div class="grid grid-cols-3 gap-1.5">
                <button
                  v-for="lt in lengthTiers"
                  :key="lt.id"
                  type="button"
                  @click="lengthTier = lt.id"
                  class="p-2 rounded-xl border text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-0.5"
                  :class="
                    lengthTier === lt.id
                      ? 'border-indigo-600 bg-indigo-50/70 text-indigo-900 font-extrabold shadow-2xs ring-1 ring-indigo-500/20'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  "
                >
                  <span class="text-xs">{{ lt.icon }} {{ lt.label }}</span>
                  <span class="text-[9px] text-slate-400 leading-tight scale-90">{{ lt.desc.split('·')[0] }}</span>
                </button>
              </div>
            </div>

            <!-- Optional Topic Keyword -->
            <div class="pt-1">
              <input
                v-model="topicInput"
                type="text"
                :placeholder="currentTemplate?.example_topic || '可选补充话题关键字，如：脾胃湿寒调理...'"
                class="w-full text-[11px] px-3 py-1.5 rounded-xl border border-slate-200 text-slate-600 placeholder:text-slate-400 focus:border-slate-400 outline-none transition"
              />
            </div>

            <!-- Generate Button -->
            <button
              type="button"
              :disabled="isGenerating"
              @click="handleGenerateMoment"
              class="w-full py-3 rounded-xl font-black text-sm text-white bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 hover:opacity-95 shadow-md shadow-emerald-500/20 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-60 flex items-center justify-center gap-2"
            >
              <span :class="{ 'animate-spin': isGenerating }">⚡</span>
              <span>{{ isGenerating ? 'AI 正在装配五维朋友圈...' : '一键智能生成朋友圈' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- =================================================================== -->
      <!-- CENTER: PIXEL-PERFECT WECHAT SIMULATOR (4.5 Cols) -->
      <!-- =================================================================== -->
      <div class="lg:col-span-4 space-y-5">
        <!-- Visual Asset Feed Toggle Pills -->
        <div class="bg-white border border-slate-200/80 rounded-2xl p-2.5 shadow-2xs flex items-center justify-between gap-1.5">
          <div class="text-[11px] font-bold text-slate-600 pl-1 shrink-0 flex items-center gap-1">
            <span>📷</span>
            <span>{{ t.product_vault?.momentsPhotoToggle || '朋友圈配图模式' }}：</span>
          </div>
          <div class="flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              @click="selectedImageMode = 'physical'"
              class="px-2.5 py-1 rounded-xl text-[11px] font-bold transition cursor-pointer shrink-0"
              :class="selectedImageMode === 'physical' ? 'bg-emerald-600 text-white shadow-2xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
            >
              {{ t.product_vault?.momentsPhysicalToggle || '📸 实物自用图' }}
            </button>
            <button
              type="button"
              @click="selectedImageMode = 'rights'"
              class="px-2.5 py-1 rounded-xl text-[11px] font-bold transition cursor-pointer shrink-0"
              :class="selectedImageMode === 'rights' ? 'bg-indigo-600 text-white shadow-2xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
            >
              {{ t.product_vault?.momentsRightsToggle || '🛡️ 服务权益图' }}
            </button>
            <button
              type="button"
              @click="selectedImageMode = 'none'"
              class="px-2.5 py-1 rounded-xl text-[11px] font-bold transition cursor-pointer shrink-0"
              :class="selectedImageMode === 'none' ? 'bg-slate-800 text-white shadow-2xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
            >
              {{ t.product_vault?.momentsNoPhotoToggle || '🚫 纯文字(不带图)' }}
            </button>
          </div>
        </div>

        <!-- WeChat Phone Device Container -->
        <div class="bg-slate-900 rounded-[36px] p-3 shadow-2xl border-4 border-slate-800 relative">
          <!-- Notch Speaker / Camera Bar -->
          <div class="w-32 h-4 bg-slate-950 rounded-full mx-auto mb-2 flex items-center justify-center gap-2">
            <div class="w-2.5 h-2.5 rounded-full bg-slate-800"></div>
            <div class="w-10 h-1 bg-slate-800 rounded-full"></div>
          </div>

          <!-- Screen Frame (Pure WeChat Moments iOS Look) -->
          <div class="bg-white rounded-[28px] overflow-hidden text-slate-800 shadow-inner min-h-[640px] flex flex-col justify-between">
            <!-- Moments Header -->
            <div class="bg-slate-50/90 border-b border-slate-200/80 px-4 py-2.5 flex items-center justify-between text-xs font-bold text-slate-700">
              <span class="flex items-center gap-1.5">
                <span>◀ 朋友圈</span>
              </span>
              <span class="font-extrabold text-[13px]">WeChat Feed</span>
              <span>📷</span>
            </div>

            <!-- Single Moments Post Item -->
            <div class="p-4 space-y-3 flex-1 flex flex-col">
              <!-- Author Header -->
              <div class="flex items-start gap-3">
                <!-- Avatar -->
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-2xs">
                  {{ currentPersona?.name?.slice(0, 1) || 'IP' }}
                </div>

                <div class="flex-1 min-w-0">
                  <div class="font-bold text-[14px] text-indigo-900 leading-tight">
                    {{ currentPersona?.name || '中医调养实践者' }}
                  </div>
                  <div class="text-[11px] text-slate-400 mt-0.5">
                    刚刚 · 广东
                  </div>
                </div>
              </div>

              <!-- Main Post Content with Real Line Calculation -->
              <div class="text-[14px] text-slate-900 leading-relaxed font-sans space-y-1 my-2">
                <!-- Display Lines -->
                <div
                  v-for="(line, idx) in visibleLines"
                  :key="idx"
                  class="relative"
                  :class="[
                    idx === 4 ? 'bg-amber-50/80 px-1.5 py-0.5 rounded border-l-2 border-amber-500 text-amber-950 font-medium' : ''
                  ]"
                >
                  <span>{{ line }}</span>
                  <!-- Highlight indicator for Line 5 hook -->
                  <span
                    v-if="idx === 4"
                    class="ml-1.5 inline-flex items-center text-[10px] text-amber-700 bg-amber-100/90 px-1 rounded font-bold"
                  >
                    🎯 第5行悬念锁控
                  </span>
                </div>

                <!-- Native WeChat "全文 / 收起" Button -->
                <div v-if="willFold" class="pt-1.5">
                  <button
                    type="button"
                    @click="isExpanded = !isExpanded"
                    class="text-indigo-700 font-bold text-xs hover:underline cursor-pointer flex items-center gap-1 select-none"
                  >
                    <span>{{ isExpanded ? '收起' : '全文' }}</span>
                    <span>{{ isExpanded ? '▲' : '▼' }}</span>
                  </button>
                </div>
              </div>

              <!-- WeChat Moments Photos Grid / Single Image -->
              <div v-if="selectedImageMode !== 'none'" class="mb-3">
                <!-- 1 Image: high-aspect single photo -->
                <div v-if="currentActiveImages.length === 1">
                  <img
                    :src="resolveImageUrl(currentActiveImages[0])"
                    alt="Moments Photo"
                    class="max-h-64 rounded-lg object-cover cursor-pointer border border-slate-200/60 shadow-xs hover:opacity-95 transition"
                    @click="openLightbox(resolveImageUrl(currentActiveImages[0]), (currentProduct?.product_name || '好物') + ' · 实物配图')"
                  />
                </div>

                <!-- 4 Images: 2x2 Grid -->
                <div
                  v-else-if="currentActiveImages.length === 4"
                  class="grid grid-cols-2 gap-1.5 w-[210px]"
                >
                  <div
                    v-for="(img, idx) in currentActiveImages"
                    :key="idx"
                    class="aspect-square rounded-md overflow-hidden bg-slate-100 cursor-pointer border border-slate-200/60 shadow-2xs group"
                    @click="openLightbox(resolveImageUrl(img), (currentProduct?.product_name || '好物') + ' · 图 #' + (idx + 1))"
                  >
                    <img :src="resolveImageUrl(img)" class="w-full h-full object-cover group-hover:scale-105 transition duration-200" />
                  </div>
                </div>

                <!-- 2, 3, 5-9 Images: Classic WeChat 3x3 Grid -->
                <div
                  v-else-if="currentActiveImages.length > 1"
                  class="grid grid-cols-3 gap-1.5 w-[240px] sm:w-[270px]"
                >
                  <div
                    v-for="(img, idx) in currentActiveImages.slice(0, 9)"
                    :key="idx"
                    class="aspect-square rounded-md overflow-hidden bg-slate-100 cursor-pointer border border-slate-200/60 shadow-2xs group"
                    @click="openLightbox(resolveImageUrl(img), (currentProduct?.product_name || '好物') + ' · 图 #' + (idx + 1))"
                  >
                    <img :src="resolveImageUrl(img)" class="w-full h-full object-cover group-hover:scale-105 transition duration-200" />
                  </div>
                </div>

                <!-- Placeholder when mode is active but product has no images yet -->
                <div
                  v-else-if="currentProduct"
                  class="p-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 text-slate-400 text-xs flex items-center gap-2"
                >
                  <span>🖼️</span>
                  <span>{{ t.product_vault?.noImagesNotice || '当前产品尚未上传配图（可在好物库中补充）' }}</span>
                </div>
              </div>

              <!-- Action Bar (Heart, Comment) -->
              <div class="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100">
                <span class="text-[11px]">公开 · 所有人可见</span>
                <div class="flex items-center gap-3">
                  <button type="button" class="hover:text-rose-500 cursor-pointer">🤍 赞</button>
                  <button type="button" class="hover:text-indigo-600 cursor-pointer">💬 评论</button>
                </div>
              </div>

              <!-- ========================================================= -->
              <!-- 评论区置顶第一枪 (Pinned Comment Lead Magnet) -->
              <!-- ========================================================= -->
              <div class="mt-4 pt-3 border-t border-slate-100 space-y-2">
                <div class="flex items-center justify-between">
                  <div class="text-[11px] font-bold text-slate-600 flex items-center gap-1.5">
                    <span class="text-amber-500">📌</span>
                    <span>评论区置顶第一枪 (截流钩子)</span>
                  </div>
                  <button
                    type="button"
                    @click="copyPinnedComment"
                    class="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 cursor-pointer transition active:scale-95"
                  >
                    📋 复制置顶话术
                  </button>
                </div>

                <!-- Comment Bubble -->
                <div class="bg-slate-50 border border-slate-200/80 rounded-xl p-3 text-xs text-slate-700 leading-relaxed flex items-start gap-2">
                  <div class="w-5 h-5 rounded-md bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                    作者
                  </div>
                  <div class="flex-1">
                    <p class="font-medium">
                      {{ momentResult?.pinned_comment || defaultPinnedComment }}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Bottom Home Indicator Bar -->
            <div class="w-24 h-1 bg-slate-300 rounded-full mx-auto my-2"></div>
          </div>
        </div>

        <!-- Live Real-Time Word & Line Count Dashboard -->
        <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-2xs space-y-3">
          <div class="flex items-center justify-between text-xs">
            <span class="font-bold text-slate-700 flex items-center gap-1.5">
              <span>📊</span>
              <span>{{ t.moments_triggers?.statWords || '字数与排版指标' }}</span>
            </span>
            <span
              class="text-[11px] font-bold px-2 py-0.5 rounded-full border transition-all"
              :class="willFold ? 'bg-amber-50 text-amber-800 border-amber-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'"
            >
              {{ willFold ? (t.moments_triggers?.statusFolded || '📱 触发折叠 (第6行后)') : (t.moments_triggers?.statusUnfolded || '🍃 直接展示 (不折叠)') }}
            </span>
          </div>

          <div class="grid grid-cols-3 gap-2 text-center">
            <div class="bg-slate-50 border border-slate-100 rounded-xl p-2">
              <div class="text-[10px] text-slate-400 font-semibold">{{ t.moments_triggers?.statWords || '字数统计' }}</div>
              <div class="text-sm font-black text-slate-800 mt-0.5">
                {{ momentResult?.character_count || currentCharacterCount }} <span class="text-[10px] font-normal text-slate-400">字</span>
              </div>
            </div>
            <div class="bg-slate-50 border border-slate-100 rounded-xl p-2">
              <div class="text-[10px] text-slate-400 font-semibold">{{ t.moments_triggers?.statLines || '预估行数' }}</div>
              <div class="text-sm font-black text-slate-800 mt-0.5">
                {{ momentResult?.estimated_lines || postLines.length }} <span class="text-[10px] font-normal text-slate-400">行</span>
              </div>
            </div>
            <div class="bg-slate-50 border border-slate-100 rounded-xl p-2">
              <div class="text-[10px] text-slate-400 font-semibold">第 5 行悬念</div>
              <div class="text-[11px] font-bold mt-1" :class="lengthTier === 'short' ? 'text-slate-500' : 'text-amber-600'">
                {{ lengthTier === 'short' ? '短篇免钩' : '👇 强悬念' }}
              </div>
            </div>
          </div>
        </div>

        <!-- Copy Feedback Toast -->
        <div
          v-if="toastMessage"
          class="bg-slate-900 text-white text-xs font-bold px-4 py-2.5 rounded-xl shadow-lg flex items-center justify-between toast-enter"
        >
          <span>✓ {{ toastMessage }}</span>
          <button @click="toastMessage = ''" class="text-slate-400 hover:text-white ml-2">✕</button>
        </div>
      </div>

      <!-- =================================================================== -->
      <!-- RIGHT: VISUAL 1:1 CANVAS EXPORTER (3.5 Cols) -->
      <!-- =================================================================== -->
      <div class="lg:col-span-4 space-y-5">
        <div class="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 class="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>🎨</span>
              <span>1:1 养生美学方图 Canvas</span>
            </h3>
            <span class="text-[10px] font-extrabold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
              1080x1080px
            </span>
          </div>

          <!-- Theme Selector -->
          <div class="flex items-center gap-1.5 text-xs font-semibold">
            <button
              type="button"
              @click="changeCanvasTheme('cream_minimal')"
              class="flex-1 py-1.5 rounded-lg border text-center transition cursor-pointer"
              :class="canvasTheme === 'cream_minimal' ? 'border-amber-600 bg-amber-50 text-amber-900 font-bold' : 'border-slate-200 text-slate-600'"
            >
              亚麻米白
            </button>
            <button
              type="button"
              @click="changeCanvasTheme('tea_amber')"
              class="flex-1 py-1.5 rounded-lg border text-center transition cursor-pointer"
              :class="canvasTheme === 'tea_amber' ? 'border-amber-600 bg-amber-50 text-amber-900 font-bold' : 'border-slate-200 text-slate-600'"
            >
              琥珀茶调
            </button>
            <button
              type="button"
              @click="changeCanvasTheme('zen_mist')"
              class="flex-1 py-1.5 rounded-lg border text-center transition cursor-pointer"
              :class="canvasTheme === 'zen_mist' ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-bold' : 'border-slate-200 text-slate-600'"
            >
              空灵禅意
            </button>
          </div>

          <!-- Canvas Preview Viewport -->
          <div class="w-full aspect-square bg-slate-100 rounded-2xl border border-slate-200/80 overflow-hidden relative shadow-inner flex items-center justify-center">
            <canvas ref="canvasRef" class="w-full h-full object-contain"></canvas>
          </div>

          <!-- Export Actions -->
          <div class="grid grid-cols-2 gap-2 pt-2">
            <button
              type="button"
              @click="handleDownloadCanvas"
              class="px-3.5 py-2.5 rounded-xl font-bold text-xs bg-slate-900 hover:bg-slate-800 text-white shadow-xs transition active:scale-95 cursor-pointer flex items-center justify-center gap-1.5"
            >
              <span>🖼️</span>
              <span>下载 1:1 方图</span>
            </button>
            <button
              type="button"
              @click="handleCopyCanvas"
              class="px-3.5 py-2.5 rounded-xl font-bold text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 shadow-2xs transition active:scale-95 cursor-pointer flex items-center justify-center gap-1.5"
            >
              <span>📋</span>
              <span>复制图片</span>
            </button>
          </div>

          <!-- Tags Preview -->
          <div v-if="momentResult && momentResult.tags && momentResult.tags.length > 0" class="pt-3 border-t border-slate-100">
            <div class="text-[11px] font-bold text-slate-500 mb-1.5">配套话题标签：</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="tag in momentResult.tags"
                :key="tag"
                class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700"
              >
                {{ tag.startsWith('#') ? tag : `#${tag}` }}
              </span>
            </div>
          </div>
        </div>

        <!-- Community Script Card (when toggled) -->
        <div v-if="activeSubMode === 'community'" class="bg-white border-2 border-indigo-200 rounded-2xl p-5 shadow-xs space-y-3">
          <div class="flex items-center justify-between">
            <h4 class="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
              <span>🎭</span>
              <span>社群发售轻剧场脚本</span>
            </h4>
            <button
              @click="handleGenerateCommunity"
              :disabled="isGeneratingCommunity"
              class="text-xs font-bold text-indigo-600 hover:underline cursor-pointer"
            >
              {{ isGeneratingCommunity ? '生成中...' : '重新生成' }}
            </button>
          </div>
          <div class="text-xs text-slate-700 whitespace-pre-wrap bg-slate-50 p-3 rounded-xl border border-slate-200 max-h-60 overflow-y-auto font-mono">
            {{ communityScript || '点击上方按钮生成社群高信任种草剧场脚本...' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Lightbox Modal for Simulator Photos -->
    <div
      v-if="lightboxOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-150"
      @click.self="lightboxOpen = false"
    >
      <div class="relative max-w-4xl max-h-[90vh] flex flex-col items-center">
        <div class="flex items-center justify-between w-full pb-2 text-white">
          <span class="text-xs font-bold truncate pr-4">{{ lightboxImageTitle || t.product_vault?.previewLightboxTitle || '朋友圈配图全屏预览' }}</span>
          <button
            type="button"
            @click="lightboxOpen = false"
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
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useI18n } from '../i18n'
import {
  fetchPersonas,
  fetchProducts,
  generateMoment,
  generateCommunity,
  fetchPrivateDomainTemplates,
  resolveImageUrl,
  type IPPersona,
  type ProductVaultItem,
  type MomentCategory,
  type TimeNarrativeMode,
  type TriggerType,
  type LengthTier,
  type GenerateMomentResponse,
  type PrivateDomainTemplate,
} from '../services/api'
import {
  renderMomentsCanvas,
  downloadMomentsCanvas,
  copyMomentsCanvasToClipboard,
} from '../utils/momentsCanvasExporter'

// I18n
const { t } = useI18n()

// Props & Expose
const props = defineProps<{
  initialTopic?: string
}>()

// State
const personas = ref<IPPersona[]>([])
const selectedPersonaId = ref<string>('')
const products = ref<ProductVaultItem[]>([])
const selectedProductId = ref<string>('')

const templates = ref<PrivateDomainTemplate[]>([])
const selectedCategory = ref<MomentCategory>('专业沉淀')
const timeNarrativeMode = ref<TimeNarrativeMode>('invisible')
const topicInput = ref<string>('')

// Trigger Source & Two-Layer Input & Length Tier
const triggerType = ref<TriggerType>('study_insight')
const rawExperience = ref<string>('')
const myTakeaway = ref<string>('')
const lengthTier = ref<LengthTier>('standard')

const triggerTypes = [
  { id: 'study_insight' as TriggerType, icon: '🌿', label: '中医/专业心得', placeholder: '例如：今天温习脏腑辨证，发现脾胃虚寒不能单靠温燥，要辨清脾阳与胃阴的微差...' },
  { id: 'reading_notes' as TriggerType, icon: '📖', label: '读书/古籍金句', placeholder: '例如：翻到《伤寒论》或《黄帝内经》里的一句话，瞬间顿悟了为什么很多人越补越虚...' },
  { id: 'case_experience' as TriggerType, icon: '👥', label: '学员/案例经历', placeholder: '例如：今天一位老学员向我吐槽，常年靠高强度断食生酮反而把气血耗空、月经失调...' },
  { id: 'daily_thought' as TriggerType, icon: '☕', label: '日常随想思考', placeholder: '例如：早起在阳台慢煮一壶老白茶，看着晨光散漫，突然有了关于节奏与内养的新体会...' },
]

const lengthTiers = [
  { id: 'short' as LengthTier, icon: '🍃', label: '精炼短篇', desc: '80-150字 · 3-5行 · 不折叠' },
  { id: 'standard' as LengthTier, icon: '🎯', label: '经典折叠', desc: '200-350字 · 第5行加钩👇 · 引导展开' },
  { id: 'deep' as LengthTier, icon: '📜', label: '深度长文', desc: '400-600字 · 10-15行 · 微散文沉浸' },
]

const currentTriggerPlaceholder = computed(() => {
  const item = triggerTypes.find(t => t.id === triggerType.value)
  return item?.placeholder || '输入具体事件、今天学习内容或读书感悟...'
})

const isGenerating = ref(false)
const isExpanded = ref(false)
const toastMessage = ref('')
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasTheme = ref<'cream_minimal' | 'tea_amber' | 'zen_mist'>('cream_minimal')

const activeSubMode = ref<'moments' | 'community'>('moments')
const isGeneratingCommunity = ref(false)
const communityScript = ref('')

// Image mode & Lightbox state
const selectedImageMode = ref<'physical' | 'rights' | 'none'>('physical')
const lightboxOpen = ref(false)
const lightboxImageUrl = ref('')
const lightboxImageTitle = ref('')

function openLightbox(url: string, title: string = '') {
  lightboxImageUrl.value = url
  lightboxImageTitle.value = title
  lightboxOpen.value = true
}

const currentActiveImages = computed<string[]>(() => {
  if (selectedImageMode.value === 'none') return []
  if (!currentProduct.value) return []

  if (selectedImageMode.value === 'physical') {
    const list: string[] = []
    if (currentProduct.value.gallery_images && currentProduct.value.gallery_images.length > 0) {
      list.push(...currentProduct.value.gallery_images)
    } else if (currentProduct.value.cover_image) {
      list.push(currentProduct.value.cover_image)
    }
    return list
  }

  if (selectedImageMode.value === 'rights') {
    return currentProduct.value.service_rights_images || []
  }

  return []
})

// Pre-defined category definitions
const momentCategories = [
  { id: '专业沉淀' as MomentCategory, icon: '🏛️', title: '专业沉淀圈', tagline: '权威认知 / 破除误区' },
  { id: '生活切片' as MomentCategory, icon: '☕', title: '生活切片圈', tagline: '烟火气日常 / 自律' },
  { id: '好物自用' as MomentCategory, icon: '📦', title: '好物自用圈', tagline: '真实自用 / 细节种草' },
  { id: '互动截流' as MomentCategory, icon: '💬', title: '互动截流圈', tagline: '痛点自测 / 引导扣1' },
  { id: '岁月反思' as MomentCategory, icon: '⏳', title: '岁月反思圈', tagline: '昔日踩坑 / 认知升级' },
]

const timeModes = [
  { id: 'invisible' as TimeNarrativeMode, label: '🍃 隐形时间 (默认)' },
  { id: 'fuzzy' as TimeNarrativeMode, label: '🍵 模糊口语 (之前)' },
  { id: 'solar_term' as TimeNarrativeMode, label: '🍂 节气时令 (深秋)' },
  { id: 'anniversary' as TimeNarrativeMode, label: '⏳ 时光对比 (两年前)' },
]

const momentResult = ref<GenerateMomentResponse | null>(null)

// Current selected objects
const currentPersona = computed(() => {
  return personas.value.find(p => p.id === selectedPersonaId.value) || personas.value[0] || null
})

const currentProduct = computed(() => {
  return products.value.find(p => p.id === selectedProductId.value) || null
})

const currentTemplate = computed(() => {
  return templates.value.find(t => t.category === selectedCategory.value) || null
})

// Line by line breakdown for WeChat simulator
const postLines = computed(() => {
  if (!momentResult.value?.text) {
    const sal = currentPersona.value?.reader_salutation || '姐妹们'
    const prod = currentProduct.value
    const exp = rawExperience.value.trim()
    const takeaway = myTakeaway.value.trim()

    if (lengthTier.value === 'short') {
      const subject = exp || (prod ? `自用的「${prod.product_name}」` : (topicInput.value || '日常温和调养'))
      const lines = [
        `${sal}，今天聊聊「${subject}」。`,
        `关于这个点最大的体悟：${takeaway || '调养从来不是一场冲刺，而是一场水滴石穿的生活修养。'}`,
      ]
      if (prod) {
        lines.push(`平时常喝「${prod.product_name}」，身心温润，放慢步子让气血自然归位🌿`)
      } else {
        lines.push('放慢步子，顺应天时，让气血和心神自然归位。')
      }
      return lines
    }

    if (prod) {
      return [
        `${sal}，今天聊聊我一直在自用的「${prod.product_name}」。`,
        exp ? `最近身边有朋友聊起：${exp}` : '在这个快节奏的时代里，我们总习惯了催促自己走得更快。',
        '但身体的信号往往很诚实，脾胃与气血是骗不了人的。',
        '很多人在调养路上反复踩坑，甚至越调越觉得心力交瘁。',
        '其实真正对味的调理，往往只需要把食材选对👇',
        `核心选用${prod.core_ingredients || '地道食材'}，温和润燥，专针对${prod.suitable_conditions || '体虚湿困'}。`,
        prod.taboos ? `不过要真诚劝退一句：${prod.taboos}，切记不宜贪多盲从。` : '第一是顺应天时，第二是温和养阳。',
        takeaway ? `我的切身体悟：${takeaway}` : `我的真实自用体会：${prod.personal_usage_experience || '入口温润甘甜，调理一段时间后整个人神清气爽。'}`,
        '把步子放慢一点，让气血和心神真正归位。',
      ]
    }
    return [
      `${sal}，今天聊聊「${exp || topicInput.value || '日常温和调养'}」。`,
      '很多时候我们总把调养想得太繁琐，其实身体要的只是一点点耐心。',
      '晨起先喝一杯温润的草本茶，比任何临时抱佛脚的补品都更抚慰脾胃。',
      '试过市面上很多速成方案，反而让舌苔越来越厚腻。',
      '很多人不知道，其实调养的底层逻辑只在这一句👇',
      takeaway ? `核心认知在于：${takeaway}` : '第一是顺应天时，不违背节律；第二是温和养阳，不盲目寒凉清热。',
      '第三也是最关键的：倾听自己的身体反应，不盲从任何绝对化的调理教条。',
      '把步子放慢一点，让气血和心神真正归位。',
    ]
  }
  return momentResult.value.text.split('\n').filter(l => l.trim().length > 0)
})

const willFold = computed(() => {
  if (momentResult.value) return momentResult.value.will_fold
  if (lengthTier.value === 'short') return false
  return postLines.value.length > 6
})

const currentCharacterCount = computed(() => {
  return postLines.value.join('').replace(/\s+/g, '').length
})

const visibleLines = computed(() => {
  if (isExpanded.value || lengthTier.value === 'short') {
    return postLines.value
  }
  // WeChat folds after line 6
  return postLines.value.slice(0, 6)
})

const defaultPinnedComment = computed(() => {
  const prod = currentProduct.value
  if (prod) {
    if (prod.conversion_hooks) {
      return `【自用好物置顶】总有姐妹问我同款「${prod.product_name}」怎么喝：${prod.conversion_hooks}。评论区或私信扣【1】免费发你一份冲泡指南🌿`
    }
    return `【自用好物置顶】私信发我【1】领取自用「${prod.product_name}」调理心得与配方明细，仅发前20位有缘姐妹~`
  }
  return '【作者置顶】平时脾虚湿重容易犯困的姐妹，私信扣【1】领自制节气内调自测表，今天先发前20位姐妹🌿'
})

// Actions
function handleSelectProduct(prod: ProductVaultItem | null) {
  if (!prod) {
    selectedProductId.value = ''
    return
  }
  selectedProductId.value = prod.id
  // If in default category or topic is empty, align to product
  if (selectedCategory.value === '专业沉淀' || selectedCategory.value === '好物自用') {
    selectedCategory.value = '好物自用'
  }
  if (!topicInput.value || topicInput.value.includes('自用') || topicInput.value === '脾虚湿阻体质调养底层逻辑') {
    topicInput.value = `我日常自用的「${prod.product_name}」真实体验`
  }
}

function handleSelectCategory(cat: MomentCategory) {
  selectedCategory.value = cat
  const tmpl = templates.value.find(t => t.category === cat)
  if (tmpl && (!topicInput.value || templates.value.some(x => x.example_topic === topicInput.value))) {
    topicInput.value = tmpl.example_topic
  }
}

async function handleGenerateMoment() {
  isGenerating.value = true
  try {
    const res = await generateMoment({
      category: selectedCategory.value,
      topic: topicInput.value || undefined,
      persona_id: selectedPersonaId.value || undefined,
      product_id: selectedProductId.value || undefined,
      time_narrative_mode: timeNarrativeMode.value,
      trigger_type: triggerType.value,
      raw_experience: rawExperience.value || undefined,
      my_takeaway: myTakeaway.value || undefined,
      length_tier: lengthTier.value,
    })
    momentResult.value = res
    isExpanded.value = false
    await nextTick()
    drawCanvas()
  } catch (err: any) {
    alert(`生成朋友圈失败: ${err.message || err}`)
  } finally {
    isGenerating.value = false
  }
}

async function handleGenerateCommunity() {
  isGeneratingCommunity.value = true
  try {
    const res = await generateCommunity({
      script_type: 'sale_theater',
      topic: topicInput.value,
      product_id: selectedProductId.value || undefined,
      persona_id: selectedPersonaId.value || undefined,
    })
    communityScript.value = res.content
  } catch (e: any) {
    alert(`生成社群脚本失败: ${e.message || e}`)
  } finally {
    isGeneratingCommunity.value = false
  }
}

function copyPinnedComment() {
  const text = momentResult.value?.pinned_comment || defaultPinnedComment.value
  navigator.clipboard.writeText(text)
  toastMessage.value = '置顶截流话术已复制到剪贴板！'
  setTimeout(() => (toastMessage.value = ''), 3000)
}

function changeCanvasTheme(theme: 'cream_minimal' | 'tea_amber' | 'zen_mist') {
  canvasTheme.value = theme
  drawCanvas()
}

let canvasRenderSequence = 0
const isDrawingCanvas = ref(false)

async function drawCanvas() {
  if (!canvasRef.value) return
  const currentSeq = ++canvasRenderSequence
  isDrawingCanvas.value = true

  const lines = postLines.value.slice(5) // takeaway points after hook

  let coverImgToUse: string | undefined = undefined
  if (selectedImageMode.value === 'physical') {
    coverImgToUse = currentProduct.value?.cover_image || currentProduct.value?.gallery_images?.[0]
  } else if (selectedImageMode.value === 'rights') {
    coverImgToUse = currentProduct.value?.service_rights_images?.[0] || currentProduct.value?.cover_image
  }

  try {
    await renderMomentsCanvas(canvasRef.value, {
      category: selectedCategory.value,
      topic: topicInput.value || (momentResult.value ? '今日调养心得' : '日常温和调养手记'),
      personaName: currentPersona.value?.name,
      salutation: currentPersona.value?.reader_salutation,
      productName: currentProduct.value?.product_name,
      productCoverImage: coverImgToUse ? resolveImageUrl(coverImgToUse) : undefined,
      lines: lines.length > 0 ? lines : postLines.value.slice(1, 5),
      hook: postLines.value[4] || '核心底层逻辑只在这一句👇',
      tags: momentResult.value?.tags || ['#中医食疗', '#内养日常', '#生活美学'],
      theme: canvasTheme.value,
    })
  } catch (err) {
    console.error('Failed to render Moments canvas:', err)
  } finally {
    if (currentSeq === canvasRenderSequence) {
      isDrawingCanvas.value = false
    }
  }
}

function onHubKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && lightboxOpen.value) {
    lightboxOpen.value = false
  }
}

function handleDownloadCanvas() {
  if (!canvasRef.value) return
  downloadMomentsCanvas(canvasRef.value, `moments-${selectedCategory.value}.png`)
  toastMessage.value = '1:1 方图已开始下载！'
  setTimeout(() => (toastMessage.value = ''), 3000)
}

async function handleCopyCanvas() {
  if (!canvasRef.value) return
  const ok = await copyMomentsCanvasToClipboard(canvasRef.value)
  if (ok) {
    toastMessage.value = '1:1 方图已成功复制到剪贴板！'
  } else {
    toastMessage.value = '浏览器不支持直接复制图片，请使用下载按钮'
  }
  setTimeout(() => (toastMessage.value = ''), 3000)
}

onMounted(async () => {
  window.addEventListener('keydown', onHubKeydown)
  try {
    const [fetchedPersonas, fetchedProducts, fetchedTemplates] = await Promise.all([
      fetchPersonas().catch(() => []),
      fetchProducts().catch(() => []),
      fetchPrivateDomainTemplates().catch(() => []),
    ])
    personas.value = fetchedPersonas
    if (fetchedPersonas.length > 0) {
      selectedPersonaId.value = fetchedPersonas[0].id
    }
    products.value = fetchedProducts
    templates.value = fetchedTemplates

    await nextTick()
    drawCanvas()
  } catch (err) {
    console.error('Failed to load initial data for Private Domain Hub:', err)
  }
})

function setTopic(topic: string) {
  topicInput.value = topic
  nextTick(() => drawCanvas())
}

defineExpose({
  setTopic,
})

watch(() => props.initialTopic, (newTopic?: string) => {
  if (newTopic) {
    setTopic(newTopic)
  }
}, { immediate: true })

watch([selectedPersonaId, selectedProductId, selectedCategory, selectedImageMode], () => {
  nextTick(() => drawCanvas())
})

onUnmounted(() => {
  window.removeEventListener('keydown', onHubKeydown)
})
</script>
