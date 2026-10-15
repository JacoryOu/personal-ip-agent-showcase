<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 overflow-y-auto glass-card-dark flex items-center justify-center p-4 sm:p-6"
      @click.self="handleClose"
    >
      <div
        class="bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-xl w-full overflow-hidden transform transition-all toast-enter"
      >
        <!-- Modal Header -->
        <div class="px-6 py-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
          <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-2xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-900 flex items-center justify-center text-xl shadow-xs">
              ⚙️
            </div>
            <div>
              <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100">
                {{ t.settingsModal.title }}
              </h2>
              <p class="text-xs text-slate-500 dark:text-slate-400">
                {{ t.settingsModal.subtitle }}
              </p>
            </div>
          </div>
          <button
            type="button"
            @click="handleClose"
            class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full p-1.5 transition-colors cursor-pointer"
            aria-label="Close"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Tab Switcher (Text LLM vs AI Image Engine) -->
        <div class="px-6 pt-3 pb-0 flex gap-2 border-b border-slate-100 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/40">
          <button
            type="button"
            @click="activeTab = 'text'"
            class="pb-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 select-none"
            :class="
              activeTab === 'text'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            "
          >
            <span>✍️</span>
            <span>{{ t.settingsModal.tabTextModel }}</span>
          </button>
          <button
            type="button"
            @click="activeTab = 'image'"
            class="pb-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 select-none"
            :class="
              activeTab === 'image'
                ? 'border-rose-600 text-rose-600 dark:text-rose-400 dark:border-rose-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            "
          >
            <span>🎨</span>
            <span>{{ t.settingsModal.tabImageModel }}</span>
            <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-extrabold border border-rose-200 dark:border-rose-800">
              Agnes 2.5
            </span>
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          <!-- Toast notification if saved or reset -->
          <div
            v-if="toastMessage"
            class="px-4 py-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-semibold flex items-center gap-2 animate-fade-in"
          >
            <span>✅</span>
            <span>{{ toastMessage }}</span>
          </div>

          <!-- TAB 1: TEXT LLM SETTINGS -->
          <div v-if="activeTab === 'text'" class="space-y-6">
            <!-- Section 1: Provider Presets -->
            <div class="space-y-2">
              <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {{ t.settingsModal.providerTab }}
              </label>
              <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <button
                  v-for="provider in PROVIDER_PRESETS"
                  :key="provider.id"
                  type="button"
                  @click="applyProviderPreset(provider)"
                  class="flex items-center gap-2 px-3 py-2.5 rounded-xl border text-left transition-all cursor-pointer select-none"
                  :class="
                    selectedProviderId === provider.id
                      ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/50 text-blue-900 dark:text-blue-200 ring-2 ring-blue-500/20 font-bold shadow-xs'
                      : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200'
                  "
                >
                  <span class="text-lg leading-none">{{ provider.icon }}</span>
                  <div class="min-w-0 flex-1">
                    <span class="text-xs truncate block">
                      {{ locale === 'zh' ? provider.nameZh : provider.nameEn }}
                    </span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Section 2: Base URL Input -->
            <div class="space-y-1.5">
              <!-- System default guidance card -->
              <div
                v-if="selectedProviderId === 'system'"
                class="p-3.5 rounded-2xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2.5 mb-2"
              >
                <span class="text-base leading-tight">💡</span>
                <div class="space-y-1 flex-1">
                  <div class="flex items-center justify-between">
                    <p class="font-bold">系统内置服务模式 (后端 .env 已就绪)</p>
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                      {{ serverHasKey ? '✅ 密钥已配置' : '⚠️ 密钥待配置' }}
                    </span>
                  </div>
                  <p class="text-[11px] opacity-85 leading-relaxed">
                    当前后端模型：<code class="px-1.5 py-0.2 rounded font-mono font-bold bg-white/80 dark:bg-slate-800">{{ serverModelName || 'deepseek-v4-flash-0731' }}</code>，
                    网关地址：<code class="px-1.5 py-0.2 rounded font-mono text-[10px] bg-white/80 dark:bg-slate-800">{{ serverBaseUrl || '系统默认' }}</code>。
                    在此模式下免填任何 Key 即可直接创作。
                  </p>
                  <p class="text-[10.5px] opacity-75 text-blue-700 dark:text-blue-300">
                    如需使用个人独立账号（如 DeepSeek 官方或阿里云百炼），请点击上方服务商预设进行自带密钥 (BYOK) 切换。
                  </p>
                </div>
              </div>

              <div class="flex items-center justify-between">
                <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                  {{ t.settingsModal.baseUrlLabel }}
                </label>
                <span v-if="selectedProviderId === 'system'" class="text-[11px] text-blue-600 font-semibold">
                  后端默认接口
                </span>
                <span v-else-if="selectedProviderId === 'ollama'" class="text-[11px] text-amber-600 font-medium">
                  本地免鉴权端口
                </span>
              </div>
              <input
                type="text"
                v-model="formBaseUrl"
                :disabled="selectedProviderId === 'system'"
                :placeholder="selectedProviderId === 'system' ? (serverBaseUrl || '使用后端 .env 预配置地址') : t.settingsModal.baseUrlPlaceholder"
                class="w-full px-3.5 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100 disabled:opacity-60 disabled:cursor-not-allowed"
              />
            </div>

            <!-- Section 3: Model Selection & Name -->
            <div class="space-y-2">
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                {{ t.settingsModal.modelLabel }}
              </label>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="m in MODEL_PRESETS"
                  :key="m.id"
                  type="button"
                  @click="selectModelPreset(m)"
                  class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer"
                  :class="
                    formModel === m.id
                      ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700'
                  "
                >
                  <span>{{ m.icon }}</span>
                  <span>{{ m.name }}</span>
                </button>
              </div>

              <div v-if="formModel === 'custom'" class="pt-1">
                <input
                  type="text"
                  v-model="formCustomModelName"
                  :placeholder="t.settingsModal.modelPlaceholder"
                  class="w-full px-3.5 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100"
                />
              </div>

              <div
                v-if="selectedProviderId !== 'system' && currentProviderRecommendedModels.length > 0"
                class="flex items-center gap-1.5 pt-1 text-[11px] text-slate-500 dark:text-slate-400 flex-wrap"
              >
                <span class="font-medium">推荐可用模型标识:</span>
                <button
                  v-for="rec in currentProviderRecommendedModels"
                  :key="rec"
                  type="button"
                  @click="selectRecommendedModel(rec)"
                  class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-blue-100 dark:hover:bg-blue-900/40 hover:text-blue-800 font-mono text-[10px] transition-colors cursor-pointer"
                >
                  {{ rec }}
                </button>
              </div>
            </div>

            <!-- Section 4: API Key with Show/Hide -->
            <div class="space-y-1.5">
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                {{ t.settingsModal.apiKeyLabel }}
              </label>
              <div class="relative">
                <input
                  :type="showApiKey ? 'text' : 'password'"
                  v-model="formApiKey"
                  :disabled="selectedProviderId === 'system'"
                  :placeholder="selectedProviderId === 'system' ? (serverHasKey ? `已读取后端保密密钥 (${serverMaskedKey || '已配置'})` : '后端未检测到密钥') : currentProviderApiKeyPlaceholder"
                  class="w-full pl-3.5 pr-10 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100 disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <button
                  v-if="selectedProviderId !== 'system'"
                  type="button"
                  @click="showApiKey = !showApiKey"
                  class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 text-sm cursor-pointer"
                  :title="showApiKey ? '隐藏 API Key' : '显示 API Key'"
                >
                  {{ showApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
              <p
                v-if="selectedProviderId !== 'system' && selectedProviderId !== 'ollama' && !formApiKey.trim()"
                class="text-[11px] text-amber-600 font-semibold flex items-center gap-1 mt-1"
              >
                <span>⚠️</span>
                <span>当前已选择 {{ locale === 'zh' ? currentProviderPreset.nameZh : currentProviderPreset.nameEn }}，请先填入有效 API Key 才能保存或测试连接。</span>
              </p>
              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                {{ t.settingsModal.apiKeyHint }}
              </p>
            </div>

            <!-- Section 5: Connection Testing Panel -->
            <div class="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-sm">🔌</span>
                  <span class="text-xs font-bold text-slate-800 dark:text-slate-200">
                    文本推理网关连通性与延迟测试
                  </span>
                </div>
                <button
                  type="button"
                  @click="runConnectionTest"
                  :disabled="isTesting"
                  class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:bg-slate-100 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs cursor-pointer"
                >
                  <svg
                    v-if="isTesting"
                    class="animate-spin -ml-0.5 h-3.5 w-3.5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                  <span>{{ isTesting ? t.settingsModal.testing : t.settingsModal.testBtn }}</span>
                </button>
              </div>

              <!-- Test Result Banner -->
              <div
                v-if="testResult"
                class="p-3 rounded-xl text-xs font-medium transition-all"
                :class="
                  testResult.success
                    ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                    : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200'
                "
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1.5 font-bold">
                    <span>{{ testResult.success ? '🟢' : '🔴' }}</span>
                    <span>{{ testResult.success ? t.settingsModal.testSuccess : t.settingsModal.testFailed }}</span>
                    <span class="font-mono text-[11px] px-1.5 py-0.2 rounded bg-white/70 dark:bg-slate-800">
                      {{ testResult.latency_ms }}ms
                    </span>
                  </div>
                  <span class="font-mono text-[10px] text-slate-500">
                    {{ testResult.model }}
                  </span>
                </div>
                <p class="mt-1 text-[11px] leading-relaxed break-words font-mono">
                  {{ testResult.message }}
                </p>
              </div>
            </div>
          </div>

          <!-- TAB 2: AI IMAGE ENGINE SETTINGS -->
          <div v-else class="space-y-6">
            <!-- Agnes Feature Spotlight Card -->
            <div class="p-4 rounded-2xl bg-gradient-to-br from-rose-50 via-pink-50 to-purple-50 dark:from-rose-950/30 dark:via-pink-950/20 dark:to-purple-950/30 border border-rose-200 dark:border-rose-900/60 shadow-xs space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-lg">✨</span>
                  <h4 class="text-xs font-black text-rose-900 dark:text-rose-200">
                    Agnes Image 2.5 Flash 旗舰生图适配
                  </h4>
                </div>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white font-black shadow-xs">
                  2K 免费超清
                </span>
              </div>
              <p class="text-[11px] text-rose-800 dark:text-rose-300 leading-relaxed">
                专为小红书 3:4 爆款大字报与微信公众号 16:9 头图定制。原生输出 1K-4K 高清画质，官方提供零费用免费生图配额。无密钥或网络故障时自动降级至高质量原生矢量意境背景。
              </p>
            </div>

            <!-- Image Provider Presets -->
            <div class="space-y-2">
              <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {{ t.settingsModal.imageProviderTab }}
              </label>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  v-for="preset in IMAGE_PROVIDER_PRESETS"
                  :key="preset.id"
                  type="button"
                  @click="applyImagePreset(preset)"
                  class="flex items-start gap-2.5 p-3 rounded-xl border text-left transition-all cursor-pointer select-none"
                  :class="
                    selectedImageProviderId === preset.id
                      ? 'border-rose-500 bg-rose-50/70 dark:bg-rose-950/40 text-rose-950 dark:text-rose-200 ring-2 ring-rose-500/20 font-bold shadow-xs'
                      : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200'
                  "
                >
                  <span class="text-xl leading-none pt-0.5">{{ preset.icon }}</span>
                  <div class="min-w-0 flex-1 space-y-1">
                    <div class="flex items-center justify-between">
                      <span class="text-xs font-bold truncate">
                        {{ locale === 'zh' ? preset.nameZh : preset.nameEn }}
                      </span>
                      <span class="text-[9px] px-1.5 py-0.2 rounded bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 font-semibold">
                        {{ locale === 'zh' ? preset.badgeZh : preset.badgeEn }}
                      </span>
                    </div>
                    <p class="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-1 leading-snug">
                      {{ locale === 'zh' ? preset.descriptionZh : preset.descriptionEn }}
                    </p>
                  </div>
                </button>
              </div>
            </div>

            <!-- Image Base URL -->
            <div class="space-y-1.5">
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                {{ t.settingsModal.imageBaseUrlLabel }}
              </label>
              <input
                type="text"
                v-model="formImageBaseUrl"
                :placeholder="t.settingsModal.imageBaseUrlPlaceholder"
                class="w-full px-3.5 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100"
              />
            </div>

            <!-- Image Model & Resolution -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                  {{ t.settingsModal.imageModelLabel }}
                </label>
                <input
                  type="text"
                  v-model="formImageModel"
                  :placeholder="t.settingsModal.imageModelPlaceholder"
                  class="w-full px-3.5 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100"
                />
              </div>

              <div class="space-y-1.5">
                <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                  {{ t.settingsModal.imageResolutionLabel }}
                </label>
                <div class="flex gap-1.5">
                  <button
                    v-for="res in ['1K', '2K', '3K', '4K']"
                    :key="res"
                    type="button"
                    @click="formImageResolution = res"
                    class="flex-1 py-2 text-xs font-bold rounded-xl border transition-all cursor-pointer text-center"
                    :class="
                      formImageResolution === res
                        ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200'
                    "
                  >
                    {{ res }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Image API Key -->
            <div class="space-y-1.5">
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-200">
                {{ t.settingsModal.imageApiKeyLabel }}
              </label>
              <div class="relative">
                <input
                  :type="showImageApiKey ? 'text' : 'password'"
                  v-model="formImageApiKey"
                  :placeholder="currentImageProviderPreset.apiKeyPlaceholder || t.settingsModal.imageApiKeyPlaceholder"
                  class="w-full pl-3.5 pr-10 py-2.5 text-xs font-mono rounded-xl border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500 transition-all bg-slate-50/30 dark:bg-slate-900 text-slate-800 dark:text-slate-100"
                />
                <button
                  type="button"
                  @click="showImageApiKey = !showImageApiKey"
                  class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 text-sm cursor-pointer"
                  :title="showImageApiKey ? '隐藏 API Key' : '显示 API Key'"
                >
                  {{ showImageApiKey ? '🙈' : '👁️' }}
                </button>
              </div>
              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                {{ t.settingsModal.imageApiKeyHint }}
              </p>
            </div>

            <!-- Image Connection Test Panel -->
            <div class="p-4 rounded-2xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200/80 dark:border-rose-900/60 space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-sm">🎨</span>
                  <span class="text-xs font-bold text-rose-900 dark:text-rose-200">
                    生图网关连通性与渲染测试
                  </span>
                </div>
                <button
                  type="button"
                  @click="runImageConnectionTest"
                  :disabled="isTestingImage"
                  class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white dark:bg-slate-800 border border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-200 hover:bg-rose-50 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs cursor-pointer"
                >
                  <svg
                    v-if="isTestingImage"
                    class="animate-spin -ml-0.5 h-3.5 w-3.5 text-rose-600"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                  <span>{{ isTestingImage ? t.settingsModal.testImageTesting : t.settingsModal.testImageBtn }}</span>
                </button>
              </div>

              <!-- Image Test Result Banner -->
              <div
                v-if="imageTestResult"
                class="p-3 rounded-xl text-xs font-medium transition-all"
                :class="
                  imageTestResult.success
                    ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                    : 'bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200'
                "
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1.5 font-bold">
                    <span>{{ imageTestResult.success ? '🟢' : '🟡' }}</span>
                    <span>{{ imageTestResult.success ? t.settingsModal.testImageSuccess : t.settingsModal.testImageFailed }}</span>
                    <span class="font-mono text-[11px] px-1.5 py-0.2 rounded bg-white/70 dark:bg-slate-800">
                      {{ imageTestResult.latency_ms }}ms
                    </span>
                  </div>
                  <span class="font-mono text-[10px] text-slate-500">
                    {{ imageTestResult.model }}
                  </span>
                </div>
                <p class="mt-1 text-[11px] leading-relaxed break-words font-mono">
                  {{ imageTestResult.message }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between gap-3">
          <button
            type="button"
            @click="handleReset"
            class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            {{ t.settingsModal.resetBtn }}
          </button>

          <div class="flex items-center gap-2">
            <button
              type="button"
              @click="handleClose"
              class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer"
            >
              {{ t.settingsModal.cancelBtn }}
            </button>
            <button
              type="button"
              @click="handleSave"
              class="px-5 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-95 shadow-md shadow-blue-500/20 transition-all cursor-pointer"
            >
              {{ t.settingsModal.saveBtn }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from '../i18n'
import {
  currentModel,
  currentProviderId,
  customApiKey,
  customBaseUrl,
  customModelName,
  serverModelName,
  serverBaseUrl,
  serverHasKey,
  serverMaskedKey,
  currentImageProviderId,
  currentImageModel,
  customImageApiKey,
  customImageBaseUrl,
  currentImageResolution,
  PROVIDER_PRESETS,
  MODEL_PRESETS,
  IMAGE_PROVIDER_PRESETS,
  saveModelSettings,
  resetModelSettings,
  saveImageSettings,
  resetImageSettings,
  type ProviderPreset,
  type ModelPreset,
  type ImageProviderPreset,
} from '../services/modelSettings'
import {
  testConnection,
  testImageConnection,
  getCurrentServerSettings,
  type ConnectionTestResult,
} from '../services/api'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const { t, locale } = useI18n()

// Active Modal Tab: 'text' | 'image'
const activeTab = ref<'text' | 'image'>('text')

// Text LLM Form states
const selectedProviderId = ref<string>(currentProviderId.value)
const formModel = ref<string>(currentModel.value)
const formCustomModelName = ref<string>(customModelName.value)
const formBaseUrl = ref<string>(customBaseUrl.value)
const formApiKey = ref<string>(customApiKey.value)
const showApiKey = ref(false)
const isTesting = ref(false)
const testResult = ref<ConnectionTestResult | null>(null)

// Image Engine Form states
const selectedImageProviderId = ref<string>(currentImageProviderId.value)
const formImageModel = ref<string>(currentImageModel.value)
const formImageBaseUrl = ref<string>(customImageBaseUrl.value)
const formImageApiKey = ref<string>(customImageApiKey.value)
const formImageResolution = ref<string>(currentImageResolution.value)
const showImageApiKey = ref(false)
const isTestingImage = ref(false)
const imageTestResult = ref<ConnectionTestResult | null>(null)

const toastMessage = ref<string | null>(null)

// Fetch backend .env settings on mount
onMounted(async () => {
  try {
    const s = await getCurrentServerSettings()
    serverModelName.value = s.model
    serverBaseUrl.value = s.base_url
    serverHasKey.value = s.api_key_configured
    serverMaskedKey.value = s.masked_api_key
  } catch {
    // Graceful fallback if backend offline
  }
})

// Watch open state to synchronize form
watch(
  () => props.isOpen,
  async (open) => {
    if (open) {
      // Text LLM sync
      selectedProviderId.value = currentProviderId.value
      formModel.value = currentModel.value
      formCustomModelName.value = customModelName.value
      formBaseUrl.value = customBaseUrl.value
      formApiKey.value = customApiKey.value
      testResult.value = null
      showApiKey.value = false

      // Image Engine sync
      selectedImageProviderId.value = currentImageProviderId.value
      formImageModel.value = currentImageModel.value
      formImageBaseUrl.value = customImageBaseUrl.value
      formImageApiKey.value = customImageApiKey.value
      formImageResolution.value = currentImageResolution.value
      imageTestResult.value = null
      showImageApiKey.value = false

      toastMessage.value = null

      try {
        const s = await getCurrentServerSettings()
        serverModelName.value = s.model
        serverBaseUrl.value = s.base_url
        serverHasKey.value = s.api_key_configured
        serverMaskedKey.value = s.masked_api_key
      } catch {
        // ignore
      }
    }
  }
)

const currentProviderPreset = computed(() => {
  return PROVIDER_PRESETS.find((p) => p.id === selectedProviderId.value) || PROVIDER_PRESETS[0]
})

const currentProviderRecommendedModels = computed(() => {
  return currentProviderPreset.value.recommendedModels
})

const currentProviderApiKeyPlaceholder = computed(() => {
  return currentProviderPreset.value.apiKeyPlaceholder || t.value.settingsModal.apiKeyPlaceholder
})

const currentImageProviderPreset = computed(() => {
  return IMAGE_PROVIDER_PRESETS.find((p) => p.id === selectedImageProviderId.value) || IMAGE_PROVIDER_PRESETS[0]
})

const applyProviderPreset = (provider: ProviderPreset) => {
  selectedProviderId.value = provider.id
  if (provider.id === 'system') {
    formBaseUrl.value = ''
    formModel.value = 'system'
    formApiKey.value = ''
    formCustomModelName.value = ''
  } else if (provider.id === 'deepseek') {
    formBaseUrl.value = provider.baseUrl
    formModel.value = 'deepseek-v3'
  } else if (provider.id === 'aliyun') {
    formBaseUrl.value = provider.baseUrl
    formModel.value = 'qwen-max'
  } else if (provider.id === 'siliconflow') {
    formBaseUrl.value = provider.baseUrl
    formModel.value = 'deepseek-v3'
  } else if (provider.id === 'ollama') {
    formBaseUrl.value = provider.baseUrl
    formModel.value = 'custom'
    formCustomModelName.value = provider.recommendedModels[0] || 'deepseek-r1:8b'
  } else if (provider.baseUrl) {
    formBaseUrl.value = provider.baseUrl
  }
}

const selectModelPreset = (m: ModelPreset) => {
  formModel.value = m.id
  if (m.id === 'system') {
    selectedProviderId.value = 'system'
    formBaseUrl.value = ''
    formApiKey.value = ''
  } else if (selectedProviderId.value === 'system') {
    selectedProviderId.value = m.defaultProviderId
    const targetProvider = PROVIDER_PRESETS.find(p => p.id === m.defaultProviderId)
    if (targetProvider?.baseUrl) {
      formBaseUrl.value = targetProvider.baseUrl
    }
  }
}

const applyImagePreset = (preset: ImageProviderPreset) => {
  selectedImageProviderId.value = preset.id
  if (preset.baseUrl) {
    formImageBaseUrl.value = preset.baseUrl
  }
  if (preset.model) {
    formImageModel.value = preset.model
  }
}

const selectRecommendedModel = (modelIdentifier: string) => {
  formModel.value = 'custom'
  formCustomModelName.value = modelIdentifier
}

const runConnectionTest = async () => {
  isTesting.value = true
  testResult.value = null

  const isSystem = selectedProviderId.value === 'system'
  const isLocal = Boolean(formBaseUrl.value && /(localhost|127\.0\.0\.1|0\.0\.0\.0|11434)/.test(formBaseUrl.value))

  // If BYOK mode on a cloud provider and user has NOT entered API Key:
  if (!isSystem && !isLocal && !formApiKey.value.trim()) {
    isTesting.value = false
    testResult.value = {
      success: false,
      latency_ms: 0,
      model: formModel.value,
      message: '未填写 API Key。测试云端第三方服务商前，请先填入有效的 API Key。',
    }
    return
  }

  const effectiveModel =
    formModel.value === 'custom'
      ? formCustomModelName.value.trim() || 'gpt-4o'
      : formModel.value

  try {
    const res = await testConnection({
      api_key: formApiKey.value.trim() || undefined,
      base_url: formBaseUrl.value.trim() || undefined,
      model: effectiveModel === 'system' ? undefined : effectiveModel,
      is_system_default: isSystem,
    })
    testResult.value = res
  } catch (err: any) {
    testResult.value = {
      success: false,
      latency_ms: 0,
      model: effectiveModel,
      message: err?.message || 'Network error connecting to test-connection endpoint',
    }
  } finally {
    isTesting.value = false
  }
}

const runImageConnectionTest = async () => {
  isTestingImage.value = true
  imageTestResult.value = null

  try {
    const res = await testImageConnection({
      api_key: formImageApiKey.value.trim() || undefined,
      base_url: formImageBaseUrl.value.trim() || undefined,
      model: formImageModel.value.trim() || undefined,
    })
    imageTestResult.value = res
  } catch (err: any) {
    imageTestResult.value = {
      success: false,
      latency_ms: 0,
      model: formImageModel.value || 'agnes-image-2.5-flash',
      message: err?.message || 'Image connection failed',
    }
  } finally {
    isTestingImage.value = false
  }
}

const handleSave = () => {
  // Save text model settings
  saveModelSettings({
    model: formModel.value,
    providerId: selectedProviderId.value,
    apiKey: formApiKey.value,
    baseUrl: formBaseUrl.value,
    customModelName: formCustomModelName.value,
  })

  // Save image engine settings
  saveImageSettings({
    providerId: selectedImageProviderId.value,
    model: formImageModel.value,
    apiKey: formImageApiKey.value,
    baseUrl: formImageBaseUrl.value,
    resolution: formImageResolution.value,
  })

  toastMessage.value = t.value.settingsModal.savedToast
  setTimeout(() => {
    emit('saved')
    emit('close')
  }, 400)
}

const handleReset = () => {
  resetModelSettings()
  resetImageSettings()

  // Reset local form states
  selectedProviderId.value = currentProviderId.value
  formModel.value = currentModel.value
  formCustomModelName.value = customModelName.value
  formBaseUrl.value = customBaseUrl.value
  formApiKey.value = customApiKey.value
  testResult.value = null

  selectedImageProviderId.value = currentImageProviderId.value
  formImageModel.value = currentImageModel.value
  formImageBaseUrl.value = customImageBaseUrl.value
  formImageApiKey.value = customImageApiKey.value
  formImageResolution.value = currentImageResolution.value
  imageTestResult.value = null

  toastMessage.value = t.value.settingsModal.resetToast
}

const handleClose = () => {
  emit('close')
}
</script>
