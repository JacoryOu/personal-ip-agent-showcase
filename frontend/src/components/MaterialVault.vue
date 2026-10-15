<template>
  <div class="space-y-6">
    <!-- Header Section -->
    <div class="relative overflow-hidden glass-card p-6 rounded-3xl border border-slate-200/80 shadow-xs scroll-reveal">
      <!-- Ambient background decoration -->
      <div class="absolute -right-16 -top-16 w-64 h-64 bg-gradient-to-br from-indigo-100/40 via-purple-100/30 to-transparent rounded-full blur-2xl pointer-events-none"></div>
      <div class="absolute -left-16 -bottom-16 w-64 h-64 bg-gradient-to-tr from-blue-100/40 via-amber-100/20 to-transparent rounded-full blur-2xl pointer-events-none"></div>

      <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-5 relative z-10">
        <div>
          <div class="flex items-center gap-3">
            <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200/60 text-blue-600 flex items-center justify-center text-xl shadow-2xs">
              🗄️
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-xl font-black text-slate-900 tracking-tight">{{ t.vault.title }}</h2>
                <span class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-blue-50 text-blue-700 border border-blue-200/80 shadow-2xs">
                  {{ filteredMaterials.length }} {{ locale === 'zh' ? '条素材' : 'items' }}
                </span>
              </div>
              <p class="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
                {{ t.vault.subtitle }}
              </p>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-wrap items-center gap-2">
          <!-- Daily Briefing Modal Button -->
          <button
            type="button"
            @click="showBriefingModal = true"
            class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all duration-200 active:scale-95 cursor-pointer relative shadow-xs"
            :class="
              briefingInfo?.unread
                ? 'bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 text-white shadow-md shadow-orange-500/25 ring-2 ring-orange-300 animate-pulse'
                : 'text-amber-900 bg-gradient-to-b from-amber-50 to-orange-50/80 hover:from-amber-100 hover:to-orange-100 border border-amber-200/80 hover:shadow-xs'
            "
          >
            <span class="text-sm">📬</span>
            <span>{{ briefingInfo?.unread ? t.briefing.unreadPill.replace('{trending}', String(briefingInfo.trending_count)).replace('{benchmark}', String(briefingInfo.benchmark_count)) : t.briefing.pillEmpty }}</span>
            <span
              v-if="briefingInfo?.unread"
              class="absolute -top-1 -right-1 flex h-2.5 w-2.5"
            >
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
            </span>
          </button>

          <!-- Benchmark Accounts & Auth Center Button -->
          <button
            type="button"
            @click="showBenchmarkAccountsModal = true"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-indigo-700 bg-gradient-to-b from-indigo-50/90 to-indigo-100/70 hover:from-indigo-100 hover:to-indigo-200/80 border border-indigo-200/80 shadow-2xs hover:shadow-indigo-500/10 transition-all active:scale-95 cursor-pointer"
          >
            <span>🎯</span>
            <span>{{ t.vault.platformAccountsBtn }}</span>
          </button>

          <!-- Collect URL Button -->
          <button
            type="button"
            @click="showCollectModal = true"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 via-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-sm shadow-blue-500/25 border border-blue-500/30 transition-all active:scale-95 cursor-pointer"
          >
            <span>🔗</span>
            <span>{{ t.vault.collectUrlBtn }}</span>
          </button>

          <!-- New Personal Note Button -->
          <button
            type="button"
            @click="showPersonalModal = true"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-purple-700 bg-gradient-to-b from-purple-50/90 to-purple-100/70 hover:from-purple-100 hover:to-purple-200/80 border border-purple-200/80 shadow-2xs hover:shadow-purple-500/10 transition-all active:scale-95 cursor-pointer"
          >
            <span>📝</span>
            <span>{{ t.vault.createPersonalBtn }}</span>
          </button>

          <!-- Refresh Trending Radar Button -->
          <button
            type="button"
            @click="handleRefreshTrending"
            :disabled="isFetchingTrending"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-amber-800 bg-gradient-to-b from-amber-50/90 to-amber-100/70 hover:from-amber-100 hover:to-amber-200/80 border border-amber-200/80 shadow-2xs hover:shadow-amber-500/10 transition-all active:scale-95 cursor-pointer disabled:opacity-50"
          >
            <span :class="{ 'animate-spin': isFetchingTrending }">⚡</span>
            <span>{{ isFetchingTrending ? (locale === 'zh' ? '正在探测...' : 'Detecting...') : t.vault.refreshTrendingBtn }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Category Tabs & Filters Bar -->
    <div class="space-y-4">
      <!-- 3 Primary Category Tabs -->
      <div class="flex items-center gap-2 border-b border-slate-200/80 pb-3 overflow-x-auto">
        <button
          type="button"
          @click="activeCategory = 'trending'"
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 cursor-pointer whitespace-nowrap active:scale-95"
          :class="activeCategory === 'trending' ? 'bg-gradient-to-r from-amber-600 to-orange-600 text-white shadow-sm shadow-amber-600/25' : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'"
        >
          <span>🔥</span>
          <span>{{ t.vault.tabTrending }}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold" :class="activeCategory === 'trending' ? 'bg-amber-800/80 text-white' : 'bg-slate-200/80 text-slate-700'">
            {{ countByType('trending') }}
          </span>
        </button>

        <button
          type="button"
          @click="activeCategory = 'benchmark'"
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 cursor-pointer whitespace-nowrap active:scale-95"
          :class="activeCategory === 'benchmark' ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm shadow-blue-600/25' : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'"
        >
          <span>🦴</span>
          <span>{{ t.vault.tabBenchmark }}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold" :class="activeCategory === 'benchmark' ? 'bg-blue-800/80 text-white' : 'bg-slate-200/80 text-slate-700'">
            {{ countByType('benchmark') }}
          </span>
        </button>

        <button
          type="button"
          @click="activeCategory = 'personal'"
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 cursor-pointer whitespace-nowrap active:scale-95"
          :class="activeCategory === 'personal' ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-sm shadow-purple-600/25' : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'"
        >
          <span>💡</span>
          <span>{{ t.vault.tabPersonal }}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold" :class="activeCategory === 'personal' ? 'bg-purple-800/80 text-white' : 'bg-slate-200/80 text-slate-700'">
            {{ countByType('personal') }}
          </span>
        </button>
      </div>

      <!-- Secondary Search & Status Filter -->
      <div class="flex flex-col sm:flex-row items-center justify-between gap-3">
        <!-- Search Bar -->
        <div class="relative w-full sm:w-80">
          <span class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 text-xs">
            🔍
          </span>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t.vault.searchPlaceholder"
            class="w-full pl-9 pr-8 py-2 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs transition-all"
          />
          <button
            v-if="searchQuery"
            type="button"
            @click="searchQuery = ''"
            class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-slate-600 text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>

        <!-- Status Filter Pills -->
        <div class="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
          <button
            v-for="st in statusOptions"
            :key="st.key"
            type="button"
            @click="selectedStatus = st.key"
            class="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer whitespace-nowrap active:scale-95"
            :class="selectedStatus === st.key ? 'bg-slate-900 text-white shadow-xs' : 'bg-white text-slate-600 hover:bg-slate-100/80 border border-slate-200/80 shadow-2xs'"
          >
            {{ st.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Alert / Toast -->
    <div
      v-if="feedbackMsg"
      class="p-3.5 rounded-2xl border text-xs font-semibold flex items-center justify-between shadow-2xs toast-enter"
      :class="feedbackType === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'"
    >
      <span class="flex items-center gap-1.5">{{ feedbackMsg }}</span>
      <button @click="feedbackMsg = ''" class="ml-2 hover:opacity-75 cursor-pointer">✕</button>
    </div>

    <!-- Materials Grid -->
    <div v-if="isLoading" class="py-20 text-center text-slate-400 bg-white/60 rounded-3xl border border-slate-200/80">
      <span class="inline-block animate-spin text-3xl mb-2">⏳</span>
      <p class="text-xs font-medium">{{ locale === 'zh' ? '正在载入素材库...' : 'Loading materials...' }}</p>
    </div>

    <div v-else-if="filteredMaterials.length === 0" class="py-20 text-center bg-white rounded-3xl border border-slate-200/80 shadow-xs scroll-fade">
      <span class="text-5xl block mb-3">{{ activeCategory === 'trending' ? '🔥' : activeCategory === 'benchmark' ? '🦴' : '💡' }}</span>
      <h3 class="text-sm font-bold text-slate-800">
        {{ activeCategory === 'trending' ? t.vault.emptyTrending : activeCategory === 'benchmark' ? t.vault.emptyBenchmark : t.vault.emptyPersonal }}
      </h3>
      <p class="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
        {{ activeCategory === 'trending' ? '点击右上角「探测全网热点」即刻捕获爆款话题' : activeCategory === 'benchmark' ? '点击「采集文章」或「对标账号」提取优质创作骨架' : '记录个人见闻与经历碎片，为二创提供活水源泉' }}
      </p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-5 items-stretch cv-auto">
      <div
        v-for="item in filteredMaterials"
        :key="item.id"
        class="bg-white rounded-3xl p-5 sm:p-6 border border-slate-200/80 shadow-xs hover:shadow-xl hover:border-slate-300/90 hover:-translate-y-0.5 transition-all duration-200 flex flex-col justify-between group h-full relative overflow-hidden scroll-reveal active:scale-[0.99]"
      >
        <div class="flex-1 flex flex-col space-y-3.5">
          <!-- Top Meta Info & Badges -->
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-1.5 flex-wrap">
              <!-- Platform Badge -->
              <span
                class="px-2.5 py-0.5 rounded-lg text-[11px] font-bold flex items-center gap-1 shadow-2xs border"
                :class="getPlatformBadgeClass(item.source_platform)"
              >
                <span>{{ getPlatformIcon(item.source_platform) }}</span>
                <span>{{ formatPlatformDisplay(item.source_platform) }}</span>
              </span>

              <!-- Status Badge -->
              <span
                class="px-2.5 py-0.5 rounded-lg text-[11px] font-semibold border shadow-2xs"
                :class="getStatusBadgeClass(item.status)"
              >
                {{ formatStatus(item.status) }}
              </span>

              <!-- Hot Value if exists -->
              <span
                v-if="item.meta_info?.hot_score || item.meta_info?.hot_value"
                class="px-2 py-0.5 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs"
              >
                🔥 {{ (item.meta_info?.hot_score || item.meta_info?.hot_value).toLocaleString() }}
              </span>
            </div>

            <!-- Delete action -->
            <button
              type="button"
              @click="handleDelete(item.id)"
              class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-300 hover:text-red-500 hover:bg-red-50 text-xs transition-all cursor-pointer opacity-80 group-hover:opacity-100"
              title="Delete material"
            >
              🗑️
            </button>
          </div>

          <!-- Title -->
          <h3 class="text-base font-bold text-slate-900 group-hover:text-blue-600 transition leading-snug">
            <a
              v-if="item.source_url"
              :href="item.source_url"
              target="_blank"
              rel="noopener noreferrer"
              class="hover:underline flex items-center gap-1.5"
            >
              <span>{{ item.title }}</span>
              <span class="text-xs text-slate-400 group-hover:text-blue-500 transition">↗</span>
            </a>
            <span v-else>{{ item.title }}</span>
          </h3>

          <!-- Author & Link Info -->
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span class="flex items-center gap-1 font-medium">👤 {{ item.source_author || '本人' }}</span>
            <span v-if="item.created_at">· 🕒 {{ formatDate(item.created_at) }}</span>
          </div>

          <!-- Cleaned Content Body Excerpt -->
          <p class="text-xs text-slate-600 line-clamp-3 leading-relaxed whitespace-pre-wrap flex-1">
            {{ item.cleaned_content }}
          </p>

          <!-- Structural Blueprint Foldout / Container -->
          <div
            v-if="item.blueprint_data"
            class="p-4 rounded-2xl bg-gradient-to-br from-amber-50/80 via-indigo-50/40 to-amber-50/60 border border-amber-200/90 shadow-2xs text-xs space-y-2.5 transition-all"
          >
            <div class="flex items-center justify-between font-bold text-amber-950">
              <span class="flex items-center gap-1.5">
                <span class="text-sm">🦴</span>
                <span class="tracking-tight">{{ item.blueprint_data.title || '提取的对标骨架' }}</span>
              </span>
              <span class="text-[10px] font-bold text-amber-800 bg-amber-100/90 border border-amber-200/80 px-2 py-0.5 rounded-lg shadow-2xs">
                {{ (item.blueprint_data.structural_stages || item.blueprint_data.key_stages || []).length }} 阶段
              </span>
            </div>

            <!-- Hook Style -->
            <div v-if="item.blueprint_data.hook_style || item.blueprint_data.opening_hook" class="flex items-start gap-1.5 text-[11px] leading-relaxed">
              <span class="font-bold text-amber-900 bg-amber-100/90 border border-amber-200/60 px-1.5 py-0.5 rounded-md shrink-0 shadow-2xs">🪝 Hook</span>
              <span class="text-slate-800 font-medium pt-0.5">{{ item.blueprint_data.opening_hook || item.blueprint_data.hook_style }}</span>
            </div>

            <!-- Emotional Arc -->
            <div v-if="item.blueprint_data.emotional_arc" class="flex items-start gap-1.5 text-[11px] leading-relaxed">
              <span class="font-bold text-indigo-900 bg-indigo-100/90 border border-indigo-200/60 px-1.5 py-0.5 rounded-md shrink-0 shadow-2xs">📈 弧线</span>
              <span class="text-slate-800 font-medium pt-0.5">{{ item.blueprint_data.emotional_arc }}</span>
            </div>

            <!-- Stages Pills -->
            <div
              v-if="(item.blueprint_data.structural_stages || item.blueprint_data.key_stages)?.length"
              class="pt-1 flex flex-wrap gap-1.5"
            >
              <span
                v-for="(stg, sIdx) in (item.blueprint_data.structural_stages || item.blueprint_data.key_stages)"
                :key="sIdx"
                class="px-2 py-0.5 rounded-lg bg-white/95 text-amber-950 text-[10px] font-semibold border border-amber-200/80 shadow-2xs"
              >
                {{ Number(sIdx) + 1 }}. {{ stg }}
              </span>
            </div>
          </div>

          <!-- Tags -->
          <div v-if="item.tags && item.tags.length > 0" class="flex flex-wrap gap-1.5 pt-1">
            <span
              v-for="tag in item.tags"
              :key="tag"
              class="px-2 py-0.5 rounded-lg text-[10px] font-medium bg-slate-100/80 text-slate-600 border border-slate-200/60"
            >
              #{{ tag }}
            </span>
          </div>
        </div>

        <!-- Card Bottom Action Bar -->
        <div class="pt-3.5 mt-3.5 border-t border-slate-100 flex items-center justify-between gap-2">
          <!-- Status toggler -->
          <select
            :value="item.status"
            @change="handleStatusChange(item.id, ($event.target as HTMLSelectElement).value)"
            class="text-xs py-1.5 px-2.5 border border-slate-200 rounded-xl text-slate-700 bg-slate-50/80 hover:bg-slate-100/80 focus:outline-none focus:ring-2 focus:ring-blue-500/20 font-medium transition cursor-pointer"
          >
            <option value="inbox">待选用 (Inbox)</option>
            <option value="used">已引用二创 (Used)</option>
            <option value="archived">已归档 (Archived)</option>
            <option value="discarded">已废弃 (Discarded)</option>
          </select>

          <!-- Primary Creation Button -->
          <button
            type="button"
            @click="handleCreateWithMaterial(item)"
            class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 via-indigo-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 shadow-sm shadow-indigo-500/20 transition-all active:scale-95 cursor-pointer"
          >
            <span>🦴</span>
            <span>{{ t.vault.createFromMaterial }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- MODAL 1: URL Collector Modal -->
    <div
      v-if="showCollectModal"
      class="fixed inset-0 z-50 glass-card-dark flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-5 border border-slate-200/80 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div class="flex items-center gap-2.5">
            <span class="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-base">🔗</span>
            <h3 class="text-base font-bold text-slate-900">{{ t.vault.collectModalTitle }}</h3>
          </div>
          <button @click="showCollectModal = false" class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer">✕</button>
        </div>

        <p class="text-xs text-slate-500 leading-relaxed">
          {{ t.vault.collectModalDesc }}
        </p>

        <div class="space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.vault.urlInputLabel }}</label>
            <input
              v-model="collectForm.url"
              type="url"
              required
              :placeholder="t.vault.urlInputPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">自定义标题 (可选)</label>
            <input
              v-model="collectForm.title"
              type="text"
              placeholder="留空则自动从文章抓取标题"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.vault.tagsLabel }}</label>
            <input
              v-model="collectForm.tagsInput"
              type="text"
              :placeholder="t.vault.tagsPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div class="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-100/90 flex items-start gap-3">
            <input
              id="extract_bp"
              v-model="collectForm.extractBlueprint"
              type="checkbox"
              class="mt-0.5 rounded text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
            />
            <label for="extract_bp" class="cursor-pointer">
              <span class="font-bold text-blue-900 block">{{ t.vault.extractBlueprintToggle }}</span>
              <span class="text-slate-500 text-[11px] block mt-0.5 leading-relaxed">{{ t.vault.extractBlueprintHint }}</span>
            </label>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
          <button
            type="button"
            @click="showCollectModal = false"
            class="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            @click="handleCollectSubmit"
            :disabled="isCollecting || !collectForm.url.trim()"
            class="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-xl text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <span v-if="isCollecting" class="animate-spin">⏳</span>
            <span>{{ isCollecting ? t.vault.collecting : t.vault.collectSubmit }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- MODAL 2: Personal Note Modal -->
    <div
      v-if="showPersonalModal"
      class="fixed inset-0 z-50 glass-card-dark flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-5 border border-slate-200/80 toast-enter">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div class="flex items-center gap-2.5">
            <span class="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center text-base">📝</span>
            <h3 class="text-base font-bold text-slate-900">{{ t.vault.personalModalTitle }}</h3>
          </div>
          <button @click="showPersonalModal = false" class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer">✕</button>
        </div>

        <div class="space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.vault.personalTitleLabel }}</label>
            <input
              v-model="personalForm.title"
              type="text"
              required
              :placeholder="t.vault.personalTitlePlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.vault.personalContentLabel }}</label>
            <textarea
              v-model="personalForm.content"
              rows="5"
              required
              :placeholder="t.vault.personalContentPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 shadow-2xs transition outline-none text-slate-800"
            ></textarea>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.vault.tagsLabel }}</label>
            <input
              v-model="personalForm.tagsInput"
              type="text"
              :placeholder="t.vault.tagsPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
          <button
            type="button"
            @click="showPersonalModal = false"
            class="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            @click="handlePersonalSubmit"
            :disabled="isSavingPersonal || !personalForm.title.trim()"
            class="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-xl text-white bg-purple-600 hover:bg-purple-700 shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <span v-if="isSavingPersonal" class="animate-spin">⏳</span>
            <span>{{ isSavingPersonal ? '保存中...' : t.vault.savePersonalBtn }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- MODAL 3: Benchmark Accounts & Platform Center Modal -->
    <BenchmarkAccountsModal
      v-if="showBenchmarkAccountsModal"
      @close="showBenchmarkAccountsModal = false"
      @materials-updated="handleMaterialsUpdated"
    />

    <!-- MODAL 4: Daily Inspiration Briefing Modal -->
    <DailyBriefingModal
      :show="showBriefingModal"
      @close="showBriefingModal = false"
      @update:show="(val: boolean) => (showBriefingModal = val)"
      @create-with-blueprint="handleBriefingCreateWithBlueprint"
      @create-with-topic="handleBriefingCreateWithTopic"
      @briefing-updated="handleBriefingUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from '../i18n'
import BenchmarkAccountsModal from './BenchmarkAccountsModal.vue'
import DailyBriefingModal from './DailyBriefingModal.vue'
import {
  fetchMaterials,
  createMaterial,
  collectUrl,
  fetchTrending,
  updateMaterial,
  deleteMaterial,
  fetchTodayBriefing,
  type DailyBriefingData,
  type Material,
} from '../services/api'

const showBriefingModal = ref(false)
const briefingInfo = ref<DailyBriefingData | null>(null)

function handleBriefingCreateWithBlueprint(payload: { blueprint: any; material: Material; topic: string }) {
  emit('create-from-material', {
    material: payload.material,
    topic: payload.topic,
    blueprint: payload.blueprint,
  })
}

function handleBriefingCreateWithTopic(topic: string) {
  const dummyMat: any = {
    id: '',
    user_id: '',
    material_type: 'trending',
    title: topic,
    cleaned_content: topic,
  }
  emit('create-from-material', {
    material: dummyMat,
    topic,
  })
}

const { t, locale } = useI18n()

const emit = defineEmits<{
  (e: 'create-from-material', payload: {
    material: Material
    topic: string
    blueprint?: any
    context?: string
  }): void
}>()

// State
const materials = ref<Material[]>([])
const isLoading = ref(false)
const activeCategory = ref<'trending' | 'benchmark' | 'personal'>('trending')
const selectedStatus = ref<string>('all')
const searchQuery = ref('')
const feedbackMsg = ref('')
const feedbackType = ref<'success' | 'error'>('success')

// Modals
const showCollectModal = ref(false)
const isCollecting = ref(false)
const collectForm = ref({
  url: '',
  title: '',
  tagsInput: '',
  extractBlueprint: true,
})

const showPersonalModal = ref(false)
const isSavingPersonal = ref(false)
const personalForm = ref({
  title: '',
  content: '',
  tagsInput: '',
})

const isFetchingTrending = ref(false)
const showBenchmarkAccountsModal = ref(false)

const handleMaterialsUpdated = async () => {
  await loadMaterials()
  activeCategory.value = 'benchmark'
}

const statusOptions = computed(() => [
  { key: 'all', label: t.value.vault.statusAll },
  { key: 'inbox', label: t.value.vault.statusInbox },
  { key: 'used', label: t.value.vault.statusUsed },
  { key: 'archived', label: t.value.vault.statusArchived },
])

const countByType = (type: string) => {
  return materials.value.filter((m) => m.material_type === type).length
}

const filteredMaterials = computed(() => {
  return materials.value.filter((m) => {
    // 1. Category match
    if (m.material_type !== activeCategory.value) {
      return false
    }
    // 2. Status match
    if (selectedStatus.value !== 'all' && m.status !== selectedStatus.value) {
      return false
    }
    // 3. Search match
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      const titleMatch = m.title.toLowerCase().includes(q)
      const contentMatch = m.cleaned_content.toLowerCase().includes(q)
      const authorMatch = (m.source_author || '').toLowerCase().includes(q)
      const tagMatch = (m.tags || []).some((tag) => tag.toLowerCase().includes(q))
      if (!titleMatch && !contentMatch && !authorMatch && !tagMatch) {
        return false
      }
    }
    return true
  })
})

const loadMaterials = async () => {
  isLoading.value = true
  try {
    materials.value = await fetchMaterials({ limit: 300 })
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to load materials'
    feedbackType.value = 'error'
  } finally {
    isLoading.value = false
  }
}

const handleRefreshTrending = async () => {
  isFetchingTrending.value = true
  feedbackMsg.value = ''
  try {
    const res = await fetchTrending({ platform: 'all', limit: 10, batch_save: true })
    await loadMaterials()
    feedbackMsg.value = locale.value === 'zh'
      ? `✓ 热点雷达探测完成，已沉淀 ${res.count} 条全网爆款话题！`
      : `✓ Trending radar completed, updated ${res.count} hot topics!`
    feedbackType.value = 'success'
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to fetch trending radar'
    feedbackType.value = 'error'
  } finally {
    isFetchingTrending.value = false
  }
}

const handleCollectSubmit = async () => {
  if (!collectForm.value.url.trim()) return
  isCollecting.value = true
  feedbackMsg.value = ''
  try {
    const tags = collectForm.value.tagsInput
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)

    await collectUrl({
      url: collectForm.value.url.trim(),
      title: collectForm.value.title.trim() || undefined,
      extract_blueprint: collectForm.value.extractBlueprint,
      tags: tags.length ? tags : undefined,
      save: true,
    })

    showCollectModal.value = false
    collectForm.value = { url: '', title: '', tagsInput: '', extractBlueprint: true }
    await loadMaterials()
    activeCategory.value = 'benchmark'
    feedbackMsg.value = locale.value === 'zh' ? '✓ 文章采集与结构骨架萃取成功，已归入对标爆款库！' : '✓ Article collected & blueprint extracted successfully!'
    feedbackType.value = 'success'
  } catch (err: any) {
    feedbackMsg.value = err.message || 'URL collection failed'
    feedbackType.value = 'error'
  } finally {
    isCollecting.value = false
  }
}

const handlePersonalSubmit = async () => {
  if (!personalForm.value.title.trim()) return
  isSavingPersonal.value = true
  feedbackMsg.value = ''
  try {
    const tags = personalForm.value.tagsInput
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)

    await createMaterial({
      title: personalForm.value.title.trim(),
      cleaned_content: personalForm.value.content.trim(),
      material_type: 'personal',
      source_platform: 'manual',
      source_author: '本人记录',
      tags,
      status: 'inbox',
    })

    showPersonalModal.value = false
    personalForm.value = { title: '', content: '', tagsInput: '' }
    await loadMaterials()
    activeCategory.value = 'personal'
    feedbackMsg.value = locale.value === 'zh' ? '✓ 个人经历碎片已成功保存入库！' : '✓ Personal note preserved in vault!'
    feedbackType.value = 'success'
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to save personal note'
    feedbackType.value = 'error'
  } finally {
    isSavingPersonal.value = false
  }
}

const handleStatusChange = async (materialId: string, newStatus: string) => {
  try {
    const updated = await updateMaterial(materialId, { status: newStatus })
    const idx = materials.value.findIndex((m) => m.id === materialId)
    if (idx !== -1) {
      materials.value[idx] = updated
    }
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to update status'
    feedbackType.value = 'error'
  }
}

const handleDelete = async (materialId: string) => {
  if (!confirm(t.value.vault.deleteConfirm)) return
  try {
    await deleteMaterial(materialId)
    materials.value = materials.value.filter((m) => m.id !== materialId)
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to delete material'
    feedbackType.value = 'error'
  }
}

const handleCreateWithMaterial = (item: Material) => {
  const context = `【参考素材溯源】
来源：${item.source_platform} · 作者：${item.source_author || '未知'}
素材标题：${item.title}
核心内容摘要：${item.cleaned_content.slice(0, 300)}`
  emit('create-from-material', {
    material: item,
    topic: item.title,
    blueprint: item.blueprint_data || undefined,
    context,
  })
}

// Visual helpers
const getPlatformBadgeClass = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200/90'
    case 'xhs':
    case 'xiaohongshu':
      return 'bg-rose-50 text-rose-700 border-rose-200/90'
    case 'zhihu':
      return 'bg-blue-50 text-blue-700 border-blue-200/90'
    case 'weibo':
      return 'bg-amber-50 text-amber-700 border-amber-200/90'
    case 'manual':
      return 'bg-purple-50 text-purple-700 border-purple-200/90'
    default:
      return 'bg-slate-50 text-slate-700 border-slate-200/90'
  }
}

const formatPlatformDisplay = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return '微信公众号'
    case 'xhs':
    case 'xiaohongshu':
      return '小红书'
    case 'zhihu':
      return '知乎'
    case 'weibo':
      return '微博'
    case 'manual':
      return '随手记'
    default:
      return p || 'manual'
  }
}

const getPlatformIcon = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return '🟢'
    case 'xhs':
    case 'xiaohongshu':
      return '📕'
    case 'zhihu':
      return '🔵'
    case 'weibo':
      return '🟡'
    case 'manual':
      return '💡'
    default:
      return '🌐'
  }
}

const getStatusBadgeClass = (s: string) => {
  switch (s) {
    case 'used':
      return 'bg-indigo-50 text-indigo-700 border border-indigo-200/90'
    case 'archived':
      return 'bg-slate-100 text-slate-600 border border-slate-200/90'
    case 'discarded':
      return 'bg-red-50 text-red-600 border border-red-200/90'
    case 'inbox':
    default:
      return 'bg-amber-50 text-amber-700 border border-amber-200/90'
  }
}

const formatStatus = (s: string) => {
  switch (s) {
    case 'used':
      return locale.value === 'zh' ? '已二创' : 'Used'
    case 'archived':
      return locale.value === 'zh' ? '已归档' : 'Archived'
    case 'discarded':
      return locale.value === 'zh' ? '已废弃' : 'Discarded'
    case 'inbox':
    default:
      return locale.value === 'zh' ? '待选用' : 'Inbox'
  }
}

const formatDate = (dateStr: string) => {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString()
  } catch {
    return dateStr
  }
}

async function refreshBriefingInfo() {
  try {
    briefingInfo.value = await fetchTodayBriefing()
  } catch (e) {
    console.error('Failed to fetch briefing info:', e)
  }
}

async function handleBriefingUpdated() {
  await Promise.all([loadMaterials(), refreshBriefingInfo()])
}

onMounted(() => {
  loadMaterials()
  refreshBriefingInfo()
})
</script>
