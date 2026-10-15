<template>
  <div
    class="fixed inset-0 z-50 glass-card-dark flex items-center justify-center p-3 sm:p-5"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-3xl max-w-5xl w-full h-[90vh] shadow-2xl flex flex-col overflow-hidden toast-enter border border-slate-200/90 relative">
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-slate-50/90 via-indigo-50/30 to-white relative overflow-hidden">
        <!-- Ambient lighting sheen -->
        <div class="absolute -right-12 -top-12 w-48 h-48 bg-gradient-to-br from-indigo-200/25 to-transparent rounded-full blur-2xl pointer-events-none"></div>

        <div class="flex items-center gap-3 relative z-10">
          <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center text-white text-xl shadow-md shadow-indigo-500/25">
            🎯
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                {{ t.benchmarkPlatform.title }}
              </h2>
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200/80 shadow-2xs">
                WeChat · XHS · Zhihu
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-0.5 leading-relaxed">
              {{ t.benchmarkPlatform.subtitle }}
            </p>
          </div>
        </div>

        <button
          type="button"
          @click="emit('close')"
          class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100/80 transition cursor-pointer relative z-10"
        >
          ✕
        </button>
      </div>

      <!-- Navigation Tabs & Action Bar -->
      <div class="px-6 py-3 bg-slate-50/80 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
        <!-- 3 Primary Tabs -->
        <div class="flex items-center gap-2">
          <button
            type="button"
            @click="activeTab = 'accounts'"
            class="px-4 py-2 rounded-xl text-xs font-bold transition-all duration-150 cursor-pointer flex items-center gap-1.5 active:scale-95"
            :class="activeTab === 'accounts' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-600/25' : 'text-slate-600 hover:bg-slate-200/70'"
          >
            <span>{{ t.benchmarkPlatform.tabAccounts }}</span>
            <span class="px-1.5 py-0.2 rounded-full text-[10px] font-bold" :class="activeTab === 'accounts' ? 'bg-indigo-800 text-white' : 'bg-slate-200 text-slate-700'">
              {{ accounts.length }}
            </span>
          </button>

          <button
            type="button"
            @click="activeTab = 'feed'"
            class="px-4 py-2 rounded-xl text-xs font-bold transition-all duration-150 cursor-pointer flex items-center gap-1.5 active:scale-95"
            :class="activeTab === 'feed' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-600/25' : 'text-slate-600 hover:bg-slate-200/70'"
          >
            <span>{{ t.benchmarkPlatform.tabFeed }}</span>
            <span v-if="selectedAccount" class="px-1.5 py-0.2 rounded-full text-[10px] font-bold" :class="activeTab === 'feed' ? 'bg-indigo-800 text-white' : 'bg-slate-200 text-slate-700'">
              {{ feedItems.length }}
            </span>
          </button>

          <button
            type="button"
            @click="activeTab = 'auth'"
            class="px-4 py-2 rounded-xl text-xs font-bold transition-all duration-150 cursor-pointer flex items-center gap-1.5 active:scale-95"
            :class="activeTab === 'auth' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-600/25' : 'text-slate-600 hover:bg-slate-200/70'"
          >
            <span>{{ t.benchmarkPlatform.tabAuth }}</span>
            <span class="relative flex h-2 w-2">
              <span v-if="hasValidCredential" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2" :class="hasValidCredential ? 'bg-emerald-500' : 'bg-amber-400'"></span>
            </span>
          </button>
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center gap-2">
          <button
            v-if="activeTab === 'accounts'"
            type="button"
            @click="showAddAccountModal = true"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm shadow-indigo-500/20 transition-all active:scale-95 cursor-pointer"
          >
            <span>+</span>
            <span>{{ t.benchmarkPlatform.addAccountBtn }}</span>
          </button>

          <button
            v-if="activeTab === 'feed' && selectedAccount"
            type="button"
            @click="refreshFeed"
            :disabled="isLoadingFeed"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 bg-white border border-slate-200/90 hover:bg-slate-50 shadow-2xs transition-all active:scale-95 cursor-pointer disabled:opacity-50"
          >
            <span :class="{ 'animate-spin': isLoadingFeed }">🔄</span>
            <span>{{ t.benchmarkPlatform.syncBtn }}</span>
          </button>
        </div>
      </div>

      <!-- Alert Notification -->
      <div
        v-if="feedbackMsg"
        class="mx-6 mt-3 p-3.5 rounded-2xl border text-xs font-semibold flex items-center justify-between shadow-2xs animate-in fade-in"
        :class="feedbackType === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'"
      >
        <span class="flex items-center gap-1.5">{{ feedbackMsg }}</span>
        <button @click="feedbackMsg = ''" class="hover:opacity-75 cursor-pointer">✕</button>
      </div>

      <!-- Main Scrollable Body Area with Sleek Scrollbar -->
      <div class="flex-1 overflow-y-auto p-6 [scrollbar-width:thin] [scrollbar-color:#cbd5e1_transparent]">
        <!-- ======================================================== -->
        <!-- TAB 1: ACCOUNTS LIST VIEW -->
        <!-- ======================================================== -->
        <div v-if="activeTab === 'accounts'" class="space-y-4">
          <!-- Platform Filter Pills -->
          <div class="flex items-center gap-2 pb-1 overflow-x-auto">
            <button
              v-for="p in platformFilters"
              :key="p.key"
              type="button"
              @click="selectedPlatformFilter = p.key"
              class="px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer whitespace-nowrap active:scale-95"
              :class="selectedPlatformFilter === p.key ? 'bg-slate-900 text-white shadow-xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200/80'"
            >
              {{ p.label }}
            </button>
          </div>

          <!-- Empty State -->
          <div
            v-if="filteredAccounts.length === 0"
            class="py-16 text-center border-2 border-dashed border-slate-200 rounded-3xl p-6 bg-slate-50/50"
          >
            <span class="text-4xl block mb-2">👥</span>
            <p class="text-xs font-bold text-slate-700">
              {{ t.benchmarkPlatform.emptyAccounts }}
            </p>
            <button
              type="button"
              @click="showAddAccountModal = true"
              class="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition active:scale-95 cursor-pointer"
            >
              <span>+</span>
              <span>{{ t.benchmarkPlatform.addAccountBtn }}</span>
            </button>
          </div>

          <!-- Accounts Cards Grid -->
          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div
              v-for="acc in filteredAccounts"
              :key="acc.id"
              class="p-5 rounded-3xl border border-slate-200/80 hover:border-indigo-400/90 bg-white shadow-xs hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 flex flex-col justify-between space-y-4 group relative overflow-hidden"
            >
              <div class="space-y-3">
                <div class="flex items-start justify-between gap-2">
                  <div class="flex items-center gap-3">
                    <div class="relative">
                      <img
                        :src="acc.avatar_url || `https://api.dicebear.com/7.x/identicon/svg?seed=${acc.account_name}`"
                        alt="Avatar"
                        class="w-12 h-12 rounded-2xl border border-slate-200 object-cover bg-slate-50 shadow-2xs"
                      />
                      <!-- High-Tech Active Status Dot -->
                      <span class="absolute -bottom-1 -right-1 flex h-3 w-3">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500 border-2 border-white"></span>
                      </span>
                    </div>

                    <div>
                      <h3 class="text-sm font-bold text-slate-900 group-hover:text-indigo-600 transition leading-snug">
                        {{ acc.account_name }}
                      </h3>
                      <div class="flex items-center gap-1.5 mt-1">
                        <span
                          class="px-2 py-0.5 rounded-md text-[10px] font-bold shadow-2xs border"
                          :class="getPlatformClass(acc.platform)"
                        >
                          {{ formatPlatformName(acc.platform) }}
                        </span>
                        <span class="text-[10px] text-slate-400 font-mono">
                          ID: {{ acc.account_id }}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    @click.stop="handleDeleteAccount(acc.id)"
                    class="w-7 h-7 rounded-lg flex items-center justify-center text-slate-300 hover:text-red-500 hover:bg-red-50 transition cursor-pointer"
                    :title="t.benchmarkPlatform.deleteAccount"
                  >
                    🗑️
                  </button>
                </div>

                <p v-if="acc.bio" class="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                  {{ acc.bio }}
                </p>

                <div class="flex items-center gap-3 text-[11px] text-slate-500 font-medium pt-0.5">
                  <span class="flex items-center gap-1">👥 {{ t.benchmarkPlatform.followers.replace('{count}', (acc.follower_count || 0).toLocaleString()) }}</span>
                  <span>·</span>
                  <span class="flex items-center gap-1">📝 {{ t.benchmarkPlatform.notesCount.replace('{count}', String(acc.notes_count || 0)) }}</span>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span class="text-[11px] text-slate-400">
                  {{ acc.last_synced_at ? t.benchmarkPlatform.lastSync.replace('{time}', new Date(acc.last_synced_at).toLocaleDateString()) : '未同步发文' }}
                </span>

                <button
                  type="button"
                  @click="inspectAccountFeed(acc)"
                  class="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-xl text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200/80 shadow-2xs transition active:scale-95 cursor-pointer"
                >
                  <span>{{ t.benchmarkPlatform.syncBtn }}</span>
                  <span>→</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- TAB 2: POST FEED & BATCH INGESTION VIEW -->
        <!-- ======================================================== -->
        <div v-else-if="activeTab === 'feed'" class="space-y-4">
          <!-- Account Switcher Bar -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-gradient-to-r from-indigo-50/80 via-purple-50/40 to-indigo-50/60 border border-indigo-100/90 shadow-2xs">
            <div class="flex items-center gap-3">
              <span class="text-2xl p-2 rounded-2xl bg-white shadow-2xs border border-indigo-100">
                {{ getPlatformIcon(selectedAccount?.platform) }}
              </span>
              <div>
                <h3 class="text-sm font-bold text-indigo-950">
                  {{ selectedAccount ? t.benchmarkPlatform.feedTitle.replace('{name}', selectedAccount.account_name) : t.benchmarkPlatform.selectAccountHint }}
                </h3>
                <p v-if="selectedAccount" class="text-[11px] text-indigo-700 mt-0.5">
                  {{ selectedAccount.bio || formatPlatformName(selectedAccount.platform) }}
                </p>
              </div>
            </div>

            <!-- Sorting & Selection Actions -->
            <div v-if="selectedAccount" class="flex flex-wrap items-center gap-2">
              <div class="flex items-center rounded-xl bg-white border border-slate-200/90 p-0.5 text-xs shadow-2xs">
                <button
                  type="button"
                  @click="setFeedSort('latest')"
                  class="px-3 py-1 rounded-lg font-medium transition cursor-pointer"
                  :class="feedSortBy === 'latest' ? 'bg-indigo-600 text-white font-bold shadow-2xs' : 'text-slate-600 hover:text-slate-900'"
                >
                  {{ t.benchmarkPlatform.sortLatest }}
                </button>
                <button
                  type="button"
                  @click="setFeedSort('hot')"
                  class="px-3 py-1 rounded-lg font-medium transition cursor-pointer"
                  :class="feedSortBy === 'hot' ? 'bg-rose-600 text-white font-bold shadow-2xs' : 'text-slate-600 hover:text-slate-900'"
                >
                  {{ t.benchmarkPlatform.sortHot }}
                </button>
              </div>

              <!-- Select All toggle -->
              <button
                type="button"
                @click="toggleSelectAll"
                class="px-3 py-1.5 rounded-xl border border-slate-200/90 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 transition active:scale-95 cursor-pointer shadow-2xs"
              >
                {{ allSelected ? t.benchmarkPlatform.deselectAll : t.benchmarkPlatform.selectAll }}
              </button>

              <!-- Batch Ingest Button -->
              <button
                type="button"
                @click="handleBatchIngest"
                :disabled="selectedFeedItemIds.length === 0 || isBatchIngesting"
                class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md shadow-indigo-500/20 transition active:scale-95 disabled:opacity-50 cursor-pointer"
              >
                <span v-if="isBatchIngesting" class="animate-spin">⏳</span>
                <span>🦴</span>
                <span>
                  {{ isBatchIngesting ? t.benchmarkPlatform.ingesting : t.benchmarkPlatform.batchIngestBtn.replace('{count}', String(selectedFeedItemIds.length)) }}
                </span>
              </button>
            </div>
          </div>

          <!-- Loading state -->
          <div v-if="isLoadingFeed" class="py-20 text-center text-slate-400 bg-slate-50/50 rounded-3xl border border-slate-200">
            <span class="inline-block animate-spin text-3xl mb-2">⏳</span>
            <p class="text-xs font-medium">{{ locale === 'zh' ? '正在连接平台拉取最新发文与互动指标...' : 'Fetching account feed...' }}</p>
          </div>

          <!-- Empty Feed -->
          <div
            v-else-if="!selectedAccount || feedItems.length === 0"
            class="py-20 text-center border-2 border-dashed border-slate-200 rounded-3xl p-6 bg-slate-50/50"
          >
            <span class="text-4xl block mb-2">📑</span>
            <p class="text-xs font-bold text-slate-700">
              {{ t.benchmarkPlatform.emptyFeed }}
            </p>
          </div>

          <!-- Feed Posts Grid with Balanced Heights -->
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
            <div
              v-for="item in feedItems"
              :key="item.id"
              class="p-5 rounded-3xl border transition-all duration-200 bg-white flex flex-col justify-between space-y-3.5 hover:shadow-md hover:-translate-y-0.5 h-full"
              :class="selectedFeedItemIds.includes(item.id) ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-indigo-50/20 shadow-xs' : 'border-slate-200/80 hover:border-slate-300'"
            >
              <div class="space-y-2 flex-1 flex flex-col">
                <!-- Checkbox & Top Tags -->
                <div class="flex items-center justify-between gap-2">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      :checked="selectedFeedItemIds.includes(item.id)"
                      @change="toggleItemSelect(item.id)"
                      class="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4 cursor-pointer"
                    />
                    <span class="text-[11px] font-bold text-slate-500 font-mono">{{ item.publish_time }}</span>
                  </label>

                  <div class="flex items-center gap-1.5">
                    <span
                      v-if="item.is_ingested"
                      class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs"
                    >
                      {{ t.benchmarkPlatform.alreadyIngested }}
                    </span>
                    <span
                      class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs"
                    >
                      🔥 {{ item.hot_score.toLocaleString() }}
                    </span>
                  </div>
                </div>

                <!-- Title -->
                <h4 class="text-sm font-bold text-slate-900 leading-snug">
                  <a
                    v-if="item.url"
                    :href="item.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="hover:text-indigo-600 hover:underline flex items-center gap-1"
                  >
                    <span>{{ item.title }}</span>
                    <span class="text-xs text-slate-400">↗</span>
                  </a>
                  <span v-else>{{ item.title }}</span>
                </h4>

                <!-- Hook / Excerpt -->
                <p class="text-xs text-slate-600 line-clamp-3 leading-relaxed flex-1 whitespace-pre-wrap">
                  {{ item.summary }}
                </p>

                <!-- Tags -->
                <div v-if="item.tags && item.tags.length" class="flex flex-wrap gap-1 pt-1">
                  <span
                    v-for="tg in item.tags"
                    :key="tg"
                    class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100/80 text-slate-600 border border-slate-200/60"
                  >
                    #{{ tg }}
                  </span>
                </div>
              </div>

              <!-- Footer Metric Bar & Single Ingest Action -->
              <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <div class="flex items-center gap-3 text-xs text-slate-500 font-medium">
                  <span title="Likes">👍 {{ item.likes.toLocaleString() }}</span>
                  <span title="Collects">⭐ {{ item.collects.toLocaleString() }}</span>
                  <span title="Shares">↗️ {{ item.shares.toLocaleString() }}</span>
                </div>

                <button
                  type="button"
                  @click="handleSingleIngest(item)"
                  :disabled="item.is_ingested || isBatchIngesting"
                  class="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 cursor-pointer disabled:opacity-50"
                  :class="item.is_ingested ? 'bg-slate-100 text-slate-400' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200/80 shadow-2xs'"
                >
                  <span>🦴</span>
                  <span>{{ item.is_ingested ? t.benchmarkPlatform.alreadyIngested : t.benchmarkPlatform.singleIngestBtn }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- TAB 3: PLATFORM AUTHORIZATION & CREDENTIALS -->
        <!-- ======================================================== -->
        <div v-else-if="activeTab === 'auth'" class="space-y-6">
          <div class="border-b border-slate-100 pb-4">
            <h3 class="text-sm font-bold text-slate-900">
              {{ t.benchmarkPlatform.authTitle }}
            </h3>
            <p class="text-xs text-slate-500 mt-1 leading-relaxed">
              {{ t.benchmarkPlatform.authSubtitle }}
            </p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
            <!-- WeChat Platform Card -->
            <div class="p-6 rounded-3xl border bg-white shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4" :class="getCardBorderClass('wechat')">
              <div class="space-y-3">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <span class="text-2xl p-1.5 rounded-xl bg-emerald-50 border border-emerald-100">🟢</span>
                    <h4 class="text-sm font-bold text-slate-900">微信公众平台</h4>
                  </div>
                  <!-- High-tech status indicator -->
                  <div class="flex items-center">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-2xs"
                      :class="getStatusBadgeClass('wechat')"
                    >
                      <span v-if="getCred('wechat')?.status === 'active'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      <span v-else-if="getCred('wechat')?.status === 'expired'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                      </span>
                      <span>{{ formatCredentialStatus('wechat') }}</span>
                    </span>
                  </div>
                </div>
                <p class="text-xs text-slate-500 leading-relaxed">
                  通过扫码或输入 MP 会话 Token，支持微信公众号文章正文抓取、原图还原与发文历史监控。
                </p>
                <div v-if="getCred('wechat')" class="text-[11px] text-slate-400 space-y-0.5 bg-slate-50 p-2.5 rounded-xl">
                  <p>绑定账号：{{ getCred('wechat')?.account_identifier || '微信作者' }}</p>
                  <p>校验时间：{{ formatTime(getCred('wechat')?.last_checked_at) }}</p>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <button
                  type="button"
                  @click="openQrModal('wechat')"
                  class="flex-1 py-2 px-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-xs shadow-emerald-500/20 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.qrLoginBtn }}
                </button>
                <button
                  type="button"
                  @click="openCookieModal('wechat')"
                  class="py-2 px-2.5 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.manualCookieBtn }}
                </button>
                <button
                  v-if="getCred('wechat')"
                  type="button"
                  @click="handleRevokeCredential(getCred('wechat')!.id)"
                  class="p-2 rounded-xl text-xs text-slate-400 hover:text-red-500 hover:bg-red-50 transition cursor-pointer"
                  title="解除授权"
                >
                  🗑️
                </button>
              </div>
            </div>

            <!-- Xiaohongshu Card -->
            <div class="p-6 rounded-3xl border bg-white shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4" :class="getCardBorderClass('xhs')">
              <div class="space-y-3">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <span class="text-2xl p-1.5 rounded-xl bg-rose-50 border border-rose-100">📕</span>
                    <h4 class="text-sm font-bold text-slate-900">小红书 (RED)</h4>
                  </div>
                  <!-- High-tech status indicator -->
                  <div class="flex items-center">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-2xs"
                      :class="getStatusBadgeClass('xhs')"
                    >
                      <span v-if="getCred('xhs')?.status === 'active'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      <span v-else-if="getCred('xhs')?.status === 'expired'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                      </span>
                      <span>{{ formatCredentialStatus('xhs') }}</span>
                    </span>
                  </div>
                </div>
                <p class="text-xs text-slate-500 leading-relaxed">
                  捕获 a1 与 web_session 凭据，支持博主图文卡片抓取、点赞收藏爆款分析与结构拆解。
                </p>
                <div v-if="getCred('xhs')" class="text-[11px] text-slate-400 space-y-0.5 bg-slate-50 p-2.5 rounded-xl">
                  <p>绑定账号：{{ getCred('xhs')?.account_identifier || '小红书创作者' }}</p>
                  <p>校验时间：{{ formatTime(getCred('xhs')?.last_checked_at) }}</p>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <button
                  type="button"
                  @click="openQrModal('xhs')"
                  class="flex-1 py-2 px-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-rose-600 to-pink-600 hover:from-rose-700 hover:to-pink-700 shadow-xs shadow-rose-500/20 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.qrLoginBtn }}
                </button>
                <button
                  type="button"
                  @click="openCookieModal('xhs')"
                  class="py-2 px-2.5 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.manualCookieBtn }}
                </button>
                <button
                  v-if="getCred('xhs')"
                  type="button"
                  @click="handleRevokeCredential(getCred('xhs')!.id)"
                  class="p-2 rounded-xl text-xs text-slate-400 hover:text-red-500 hover:bg-red-50 transition cursor-pointer"
                  title="解除授权"
                >
                  🗑️
                </button>
              </div>
            </div>

            <!-- Zhihu Card -->
            <div class="p-6 rounded-3xl border bg-white shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4" :class="getCardBorderClass('zhihu')">
              <div class="space-y-3">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <span class="text-2xl p-1.5 rounded-xl bg-blue-50 border border-blue-100">🔵</span>
                    <h4 class="text-sm font-bold text-slate-900">知乎专栏 / 大V</h4>
                  </div>
                  <!-- High-tech status indicator -->
                  <div class="flex items-center">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-2xs"
                      :class="getStatusBadgeClass('zhihu')"
                    >
                      <span v-if="getCred('zhihu')?.status === 'active'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      <span v-else-if="getCred('zhihu')?.status === 'expired'" class="relative flex h-2 w-2 mr-1.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                      </span>
                      <span>{{ formatCredentialStatus('zhihu') }}</span>
                    </span>
                  </div>
                </div>
                <p class="text-xs text-slate-500 leading-relaxed">
                  通过 z_c0 凭据支持知乎专栏深度文章与高赞回答采集，深度萃取论证逻辑。
                </p>
                <div v-if="getCred('zhihu')" class="text-[11px] text-slate-400 space-y-0.5 bg-slate-50 p-2.5 rounded-xl">
                  <p>绑定账号：{{ getCred('zhihu')?.account_identifier || '知乎大V' }}</p>
                  <p>校验时间：{{ formatTime(getCred('zhihu')?.last_checked_at) }}</p>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <button
                  type="button"
                  @click="openQrModal('zhihu')"
                  class="flex-1 py-2 px-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-xs shadow-blue-500/20 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.qrLoginBtn }}
                </button>
                <button
                  type="button"
                  @click="openCookieModal('zhihu')"
                  class="py-2 px-2.5 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition active:scale-95 cursor-pointer"
                >
                  {{ t.benchmarkPlatform.manualCookieBtn }}
                </button>
                <button
                  v-if="getCred('zhihu')"
                  type="button"
                  @click="handleRevokeCredential(getCred('zhihu')!.id)"
                  class="p-2 rounded-xl text-xs text-slate-400 hover:text-red-500 hover:bg-red-50 transition cursor-pointer"
                  title="解除授权"
                >
                  🗑️
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Bar -->
      <div class="px-6 py-3.5 border-t border-slate-200/80 flex items-center justify-between bg-slate-50/80 text-xs">
        <span class="text-slate-400 flex items-center gap-1.5">
          <span>🔒</span>
          <span>本地沙箱隔离防护 · 所有 Session 凭据绝不上传至第三方云端</span>
        </span>
        <button
          type="button"
          @click="emit('close')"
          class="px-4 py-2 rounded-xl font-bold text-slate-700 bg-white border border-slate-200/90 hover:bg-slate-100 transition active:scale-95 cursor-pointer shadow-2xs"
        >
          {{ t.benchmarkPlatform.close }}
        </button>
      </div>
    </div>

    <!-- ======================================================== -->
    <!-- MODAL: ADD BENCHMARK ACCOUNT -->
    <!-- ======================================================== -->
    <div
      v-if="showAddAccountModal"
      class="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div class="bg-white rounded-3xl max-w-md w-full p-6 sm:p-7 shadow-2xl space-y-4 border border-slate-200/80 animate-in fade-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-sm font-bold text-slate-900">
            {{ t.benchmarkPlatform.modalAddTitle }}
          </h3>
          <button @click="showAddAccountModal = false" class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer">✕</button>
        </div>

        <div class="space-y-3.5 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.benchmarkPlatform.platformLabel }}</label>
            <select
              v-model="addForm.platform"
              class="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            >
              <option value="wechat">{{ t.benchmarkPlatform.platformWechat }}</option>
              <option value="xhs">{{ t.benchmarkPlatform.platformXhs }}</option>
              <option value="zhihu">{{ t.benchmarkPlatform.platformZhihu }}</option>
            </select>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.benchmarkPlatform.accountNameLabel }} *</label>
            <input
              v-model="addForm.account_name"
              type="text"
              required
              :placeholder="t.benchmarkPlatform.accountNamePlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.benchmarkPlatform.accountUrlLabel }}</label>
            <input
              v-model="addForm.home_url"
              type="url"
              :placeholder="t.benchmarkPlatform.accountUrlPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.benchmarkPlatform.bioLabel }}</label>
            <textarea
              v-model="addForm.bio"
              rows="2"
              :placeholder="t.benchmarkPlatform.bioPlaceholder"
              class="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
          <button
            type="button"
            @click="showAddAccountModal = false"
            class="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            @click="handleAddAccountSubmit"
            :disabled="!addForm.account_name.trim()"
            class="px-4 py-2 text-xs font-bold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            确认追踪
          </button>
        </div>
      </div>
    </div>

    <!-- ======================================================== -->
    <!-- MODAL: QR CODE LOGIN & POLLING -->
    <!-- ======================================================== -->
    <div
      v-if="showQrModal"
      class="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div class="bg-white rounded-3xl max-w-sm w-full p-6 sm:p-7 shadow-2xl space-y-4 border border-slate-200/80 text-center animate-in fade-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between border-b border-slate-100 pb-2.5">
          <h3 class="text-sm font-bold text-slate-900">
            {{ formatPlatformName(currentQrPlatform) }} {{ t.benchmarkPlatform.qrModalTitle }}
          </h3>
          <button @click="closeQrModal" class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer">✕</button>
        </div>

        <p class="text-xs text-slate-600 font-medium px-2 leading-relaxed">
          {{ qrInstructions || t.benchmarkPlatform.qrModalSubtitle }}
        </p>

        <!-- QR Code Visual -->
        <div class="flex justify-center p-4 bg-slate-50/80 rounded-3xl border border-slate-100 shadow-inner">
          <img
            v-if="qrCodeData"
            :src="qrCodeData"
            alt="QR Code"
            class="w-52 h-52 object-contain rounded-xl"
          />
          <div v-else class="w-52 h-52 flex items-center justify-center text-slate-400 text-xs">
            <span class="animate-spin text-2xl">⏳</span>
          </div>
        </div>

        <!-- Status & Timer -->
        <div class="space-y-1">
          <div
            class="flex items-center justify-center gap-2 text-xs font-bold"
            :class="qrStatus === 'confirmed' ? 'text-emerald-600' : qrStatus === 'scanned' ? 'text-indigo-600' : 'text-slate-700'"
          >
            <span v-if="qrStatus === 'pending_login'" class="relative flex h-2.5 w-2.5">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
            </span>
            <span v-else-if="qrStatus === 'scanned'" class="relative flex h-2.5 w-2.5">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
            </span>
            <span v-else-if="qrStatus === 'confirmed'" class="text-sm font-black text-emerald-600">✓</span>
            <span>{{ qrStatusMessage }}</span>
          </div>

          <p v-if="qrSecondsLeft > 0 && qrStatus === 'pending_login'" class="text-[11px] text-slate-400 font-mono">
            {{ t.benchmarkPlatform.qrExpireTimer.replace('{sec}', String(qrSecondsLeft)) }}
          </p>
        </div>

        <!-- Action Buttons -->
        <div class="pt-2 border-t border-slate-100 space-y-2">
          <button
            type="button"
            @click="handleSimulateQrConfirm"
            :disabled="qrStatus === 'confirmed'"
            class="w-full py-2 px-3 rounded-xl text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200/80 transition active:scale-95 cursor-pointer disabled:opacity-50"
          >
            {{ t.benchmarkPlatform.qrSimulateBtn }}
          </button>

          <button
            type="button"
            @click="switchToManualCookie"
            class="w-full py-1.5 px-3 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition active:scale-95 cursor-pointer"
          >
            🔑 {{ t.benchmarkPlatform.manualCookieBtn }}
          </button>

          <button
            v-if="qrStatus === 'expired'"
            type="button"
            @click="openQrModal(currentQrPlatform)"
            class="w-full py-1.5 px-3 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition active:scale-95 cursor-pointer"
          >
            {{ t.benchmarkPlatform.refreshQrBtn }}
          </button>
        </div>
      </div>
    </div>

    <!-- ======================================================== -->
    <!-- MODAL: MANUAL COOKIE ENTRY -->
    <!-- ======================================================== -->
    <div
      v-if="showCookieModal"
      class="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div class="bg-white rounded-3xl max-w-md w-full p-6 sm:p-7 shadow-2xl space-y-4 border border-slate-200/80 animate-in fade-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 class="text-sm font-bold text-slate-900">
            {{ formatPlatformName(currentCookiePlatform) }} {{ t.benchmarkPlatform.cookieModalTitle }}
          </h3>
          <button @click="showCookieModal = false" class="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer">✕</button>
        </div>

        <div class="space-y-3.5 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">{{ t.benchmarkPlatform.cookieLabel }} *</label>
            <textarea
              v-model="cookieText"
              rows="5"
              required
              :placeholder="t.benchmarkPlatform.cookiePlaceholder"
              class="w-full px-3.5 py-2.5 font-mono text-[11px] border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            ></textarea>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1.5">账号备注 / 昵称 (可选)</label>
            <input
              v-model="cookieIdentifier"
              type="text"
              placeholder="例如：主号、测评大V号"
              class="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs transition outline-none text-slate-800"
            />
          </div>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
          <button
            type="button"
            @click="showCookieModal = false"
            class="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            @click="handleSaveCookieSubmit"
            :disabled="!cookieText.trim() || isSavingCookie"
            class="px-4 py-2 text-xs font-bold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            {{ t.benchmarkPlatform.cookieSaveBtn }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from '../i18n'
import {
  fetchPlatformCredentials,
  startPlatformQrLogin,
  checkPlatformQrStatus,
  simulateConfirmPlatformQr,
  saveManualCookies,
  deletePlatformCredential,
  fetchBenchmarkAccounts,
  createBenchmarkAccount,
  deleteBenchmarkAccount,
  fetchAccountFeed,
  batchIngestFeedPosts,
  type PlatformCredential,
  type BenchmarkAccount,
  type FeedItem,
} from '../services/api'

const { t, locale } = useI18n()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'materials-updated'): void
}>()

// Navigation state
const activeTab = ref<'accounts' | 'feed' | 'auth'>('accounts')
const feedbackMsg = ref('')
const feedbackType = ref<'success' | 'error'>('success')

// Credentials state
const credentials = ref<PlatformCredential[]>([])

// Accounts state
const accounts = ref<BenchmarkAccount[]>([])
const selectedPlatformFilter = ref<string>('all')
const selectedAccount = ref<BenchmarkAccount | null>(null)

// Feed state
const feedItems = ref<FeedItem[]>([])
const isLoadingFeed = ref(false)
const feedSortBy = ref<'latest' | 'hot'>('latest')
const selectedFeedItemIds = ref<string[]>([])
const isBatchIngesting = ref(false)

// Modals
const showAddAccountModal = ref(false)
const addForm = ref({
  platform: 'wechat',
  account_name: '',
  home_url: '',
  bio: '',
})

// QR Login Modal
const showQrModal = ref(false)
const currentQrPlatform = ref<string>('wechat')
const currentSessionKey = ref<string>('')
const qrCodeData = ref<string>('')
const qrStatus = ref<string>('pending_login')
const qrStatusMessage = ref<string>('')
const qrInstructions = ref<string>('')
const qrSecondsLeft = ref<number>(180)
let qrTimer: any = null
let qrPollTimer: any = null

// Manual Cookie Modal
const showCookieModal = ref(false)
const currentCookiePlatform = ref<string>('wechat')
const cookieText = ref<string>('')
const cookieIdentifier = ref<string>('')
const isSavingCookie = ref(false)

const platformFilters = computed(() => [
  { key: 'all', label: locale.value === 'zh' ? '全部平台' : 'All' },
  { key: 'wechat', label: '🟢 微信公众号' },
  { key: 'xhs', label: '📕 小红书' },
  { key: 'zhihu', label: '🔵 知乎' },
])

const filteredAccounts = computed(() => {
  if (selectedPlatformFilter.value === 'all') return accounts.value
  return accounts.value.filter((a) => a.platform === selectedPlatformFilter.value)
})

const hasValidCredential = computed(() => {
  return credentials.value.some((c) => c.status === 'active')
})

const allSelected = computed(() => {
  return feedItems.value.length > 0 && selectedFeedItemIds.value.length === feedItems.value.length
})

// Data Loaders
const loadCredentials = async () => {
  try {
    credentials.value = await fetchPlatformCredentials()
  } catch (err: any) {
    console.warn('Failed to load credentials', err)
  }
}

const loadAccounts = async () => {
  try {
    accounts.value = await fetchBenchmarkAccounts()
    if (!selectedAccount.value && accounts.value.length > 0) {
      selectedAccount.value = accounts.value[0]
    }
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to load accounts'
    feedbackType.value = 'error'
  }
}

const inspectAccountFeed = async (acc: BenchmarkAccount) => {
  selectedAccount.value = acc
  activeTab.value = 'feed'
  await loadFeed()
}

const loadFeed = async () => {
  if (!selectedAccount.value) return
  isLoadingFeed.value = true
  feedbackMsg.value = ''
  selectedFeedItemIds.value = []
  try {
    const res = await fetchAccountFeed(selectedAccount.value.id, feedSortBy.value, 20)
    feedItems.value = res.items
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to fetch feed'
    feedbackType.value = 'error'
  } finally {
    isLoadingFeed.value = false
  }
}

const refreshFeed = async () => {
  await loadFeed()
}

const setFeedSort = async (sort: 'latest' | 'hot') => {
  if (feedSortBy.value === sort) return
  feedSortBy.value = sort
  await loadFeed()
}

// Ingestion Handlers
const toggleSelectAll = () => {
  if (allSelected.value) {
    selectedFeedItemIds.value = []
  } else {
    selectedFeedItemIds.value = feedItems.value.map((i) => i.id)
  }
}

const toggleItemSelect = (id: string) => {
  const idx = selectedFeedItemIds.value.indexOf(id)
  if (idx !== -1) {
    selectedFeedItemIds.value.splice(idx, 1)
  } else {
    selectedFeedItemIds.value.push(id)
  }
}

const handleBatchIngest = async () => {
  const targetItems = feedItems.value.filter((i) => selectedFeedItemIds.value.includes(i.id))
  if (!targetItems.length) return
  isBatchIngesting.value = true
  feedbackMsg.value = ''
  try {
    const res = await batchIngestFeedPosts({
      items: targetItems,
      extract_blueprint: true,
      category: 'benchmark',
      tags: ['对标拆解', selectedAccount.value?.account_name || ''],
    })
    // Mark items as ingested
    feedItems.value.forEach((item) => {
      if (selectedFeedItemIds.value.includes(item.id)) {
        item.is_ingested = true
      }
    })
    selectedFeedItemIds.value = []
    feedbackMsg.value = t.value.benchmarkPlatform.ingestSuccess.replace('{count}', String(res.count))
    feedbackType.value = 'success'
    emit('materials-updated')
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Batch ingestion failed'
    feedbackType.value = 'error'
  } finally {
    isBatchIngesting.value = false
  }
}

const handleSingleIngest = async (item: FeedItem) => {
  isBatchIngesting.value = true
  feedbackMsg.value = ''
  try {
    await batchIngestFeedPosts({
      items: [item],
      extract_blueprint: true,
      category: 'benchmark',
      tags: ['对标拆解', item.author],
    })
    item.is_ingested = true
    feedbackMsg.value = t.value.benchmarkPlatform.ingestSuccess.replace('{count}', '1')
    feedbackType.value = 'success'
    emit('materials-updated')
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Ingestion failed'
    feedbackType.value = 'error'
  } finally {
    isBatchIngesting.value = false
  }
}

// Account Creation & Deletion
const handleAddAccountSubmit = async () => {
  if (!addForm.value.account_name.trim()) return
  try {
    const newAcc = await createBenchmarkAccount({
      platform: addForm.value.platform,
      account_name: addForm.value.account_name.trim(),
      home_url: addForm.value.home_url.trim() || undefined,
      bio: addForm.value.bio.trim() || undefined,
    })
    accounts.value.unshift(newAcc)
    selectedAccount.value = newAcc
    showAddAccountModal.value = false
    addForm.value = { platform: 'wechat', account_name: '', home_url: '', bio: '' }
    feedbackMsg.value = `✓ 成功追踪对标账号「${newAcc.account_name}」！`
    feedbackType.value = 'success'
    activeTab.value = 'feed'
    await loadFeed()
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to add account'
    feedbackType.value = 'error'
  }
}

const handleDeleteAccount = async (id: string) => {
  if (!confirm('确定停止追踪并移除该对标账号吗？')) return
  try {
    await deleteBenchmarkAccount(id)
    accounts.value = accounts.value.filter((a) => a.id !== id)
    if (selectedAccount.value?.id === id) {
      selectedAccount.value = accounts.value[0] || null
      if (selectedAccount.value) {
        await loadFeed()
      } else {
        feedItems.value = []
      }
    }
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to delete account'
    feedbackType.value = 'error'
  }
}

// QR Code Login Flow
const openQrModal = async (plat: string) => {
  currentQrPlatform.value = plat
  showQrModal.value = true
  qrStatus.value = 'pending_login'
  qrStatusMessage.value = t.value.benchmarkPlatform.qrWaiting
  qrInstructions.value = ''
  qrSecondsLeft.value = 180
  qrCodeData.value = ''
  clearInterval(qrTimer)
  clearInterval(qrPollTimer)

  try {
    const res = await startPlatformQrLogin(plat)
    currentSessionKey.value = res.session_key
    qrCodeData.value = res.qr_code_data
    qrSecondsLeft.value = res.expires_in || 180
    qrInstructions.value = res.instructions || (plat === 'wechat' ? '请使用绑定了公众号的微信扫码并在手机上点击确认登录' : '请使用手机 App 扫码确认')

    // Countdown
    qrTimer = setInterval(() => {
      qrSecondsLeft.value--
      if (qrSecondsLeft.value <= 0) {
        clearInterval(qrTimer)
        clearInterval(qrPollTimer)
        qrStatus.value = 'expired'
        qrStatusMessage.value = '二维码已过期，请重新刷新'
      }
    }, 1000)

    // Polling every 2000ms (2 seconds)
    qrPollTimer = setInterval(async () => {
      if (!showQrModal.value || qrStatus.value === 'confirmed' || qrStatus.value === 'expired') {
        clearInterval(qrPollTimer)
        return
      }
      try {
        const pollRes = await checkPlatformQrStatus(currentSessionKey.value)
        if (!showQrModal.value) return

        if (pollRes.status === 'confirmed') {
          clearInterval(qrPollTimer)
          clearInterval(qrTimer)
          qrStatus.value = 'confirmed'
          qrStatusMessage.value = pollRes.message || '✓ 授权成功！已连接'
          await loadCredentials()
          feedbackMsg.value = `✓ ${formatPlatformName(plat)} 登录授权成功！已连接`
          feedbackType.value = 'success'
          setTimeout(() => {
            showQrModal.value = false
          }, 1500)
        } else if (pollRes.status === 'scanned') {
          qrStatus.value = 'scanned'
          qrStatusMessage.value = pollRes.message || '已在手机上扫码，请在手机端点击确认登录'
        } else if (pollRes.status === 'expired') {
          clearInterval(qrPollTimer)
          clearInterval(qrTimer)
          qrStatus.value = 'expired'
          qrStatusMessage.value = pollRes.message || '二维码已过期，请刷新重新扫描'
        } else if (pollRes.message) {
          qrStatusMessage.value = pollRes.message
        }
      } catch (err) {
        console.warn('QR poll error', err)
      }
    }, 2000)
  } catch (err: any) {
    qrStatus.value = 'expired'
    qrStatusMessage.value = err.message || '生成二维码失败，请刷新或使用手动录入 Cookie'
  }
}

const handleSimulateQrConfirm = async () => {
  if (!currentSessionKey.value) return
  try {
    await simulateConfirmPlatformQr(currentSessionKey.value)
    // Next poll will see confirmed
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Simulation failed'
  }
}

const closeQrModal = () => {
  showQrModal.value = false
  clearInterval(qrTimer)
  clearInterval(qrPollTimer)
}

const switchToManualCookie = () => {
  const plat = currentQrPlatform.value
  closeQrModal()
  openCookieModal(plat)
}

// Manual Cookie Modal
const openCookieModal = (plat: string) => {
  currentCookiePlatform.value = plat
  cookieText.value = ''
  cookieIdentifier.value = ''
  showCookieModal.value = true
}

const handleSaveCookieSubmit = async () => {
  if (!cookieText.value.trim()) return
  isSavingCookie.value = true
  try {
    await saveManualCookies({
      platform: currentCookiePlatform.value,
      cookies: cookieText.value.trim(),
      account_identifier: cookieIdentifier.value.trim() || undefined,
    })
    showCookieModal.value = false
    await loadCredentials()
    feedbackMsg.value = `✓ ${formatPlatformName(currentCookiePlatform.value)} Cookie 凭据保存成功！`
    feedbackType.value = 'success'
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to save cookies'
    feedbackType.value = 'error'
  } finally {
    isSavingCookie.value = false
  }
}

const handleRevokeCredential = async (credId: string) => {
  if (!confirm('确定解除该平台的授权凭据吗？')) return
  try {
    await deletePlatformCredential(credId)
    await loadCredentials()
    feedbackMsg.value = '✓ 已成功解除该平台授权凭据'
    feedbackType.value = 'success'
  } catch (err: any) {
    feedbackMsg.value = err.message || 'Failed to revoke credential'
    feedbackType.value = 'error'
  }
}

// Visual Helpers
const getCred = (plat: string) => {
  return credentials.value.find((c) => c.platform.toLowerCase() === plat.toLowerCase())
}

const formatCredentialStatus = (plat: string) => {
  const c = getCred(plat)
  if (!c) return t.value.benchmarkPlatform.unauthorizedBadge
  if (c.status === 'active') return locale.value === 'zh' ? '✓ 已连接' : '✓ Connected'
  if (c.status === 'expired') return t.value.benchmarkPlatform.expiredBadge
  return c.status
}

const getStatusBadgeClass = (plat: string) => {
  const c = getCred(plat)
  if (!c) return 'bg-slate-100 text-slate-600 border border-slate-200/90'
  if (c.status === 'active') return 'bg-emerald-50 text-emerald-700 border border-emerald-200/90'
  return 'bg-amber-50 text-amber-700 border border-amber-200/90'
}

const getCardBorderClass = (plat: string) => {
  const c = getCred(plat)
  if (c?.status === 'active') return 'border-emerald-200/90 ring-1 ring-emerald-100/80 bg-gradient-to-b from-emerald-50/20 to-white'
  if (c?.status === 'expired') return 'border-amber-200/90 ring-1 ring-amber-100/80 bg-gradient-to-b from-amber-50/20 to-white'
  return 'border-slate-200/80'
}

const formatPlatformName = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return '微信公众平台'
    case 'xhs':
      return '小红书 (RED)'
    case 'zhihu':
      return '知乎'
    default:
      return p || 'Web'
  }
}

const getPlatformClass = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return 'bg-emerald-50 text-emerald-800 border-emerald-200/90'
    case 'xhs':
      return 'bg-rose-50 text-rose-800 border-rose-200/90'
    case 'zhihu':
      return 'bg-blue-50 text-blue-800 border-blue-200/90'
    default:
      return 'bg-slate-50 text-slate-700 border-slate-200/90'
  }
}

const getPlatformIcon = (p?: string) => {
  switch (p?.toLowerCase()) {
    case 'wechat':
      return '🟢'
    case 'xhs':
      return '📕'
    case 'zhihu':
      return '🔵'
    default:
      return '🌐'
  }
}

const formatTime = (tStr?: string) => {
  if (!tStr) return '无'
  try {
    return new Date(tStr).toLocaleString()
  } catch {
    return tStr
  }
}

onMounted(async () => {
  await Promise.all([loadCredentials(), loadAccounts()])
  if (selectedAccount.value) {
    await loadFeed()
  }
})

onUnmounted(() => {
  clearInterval(qrTimer)
  clearInterval(qrPollTimer)
})
</script>
