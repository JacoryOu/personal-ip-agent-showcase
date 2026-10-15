<template>
  <div class="space-y-8">
    <!-- Active Blueprint Banner (if loaded) -->
    <div
      v-if="activeBlueprint"
      class="max-w-4xl mx-auto rounded-2xl bg-gradient-to-r from-amber-500/10 via-orange-500/5 to-amber-500/10 glass-card border border-amber-300/70 shadow-xs overflow-hidden transition-all duration-300 scroll-reveal"
    >
      <div class="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3.5 min-w-0">
          <div class="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-900 border border-amber-300/80 flex items-center justify-center text-xl shrink-0 shadow-2xs">
            🦴
          </div>
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="inline-flex items-center gap-1.5 text-xs font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-200/90 text-amber-900 border border-amber-300/80 shadow-2xs">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse"></span>
                <span>🦴 正在基于骨架二创</span>
              </span>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-100/80 text-amber-800 border border-amber-200">
                Hook: {{ activeBlueprint.hook_style || '悬念反转' }}
              </span>
              <span v-if="activeBlueprint.emotional_arc" class="text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-100/80 text-amber-800 border border-amber-200">
                情绪弧线: {{ activeBlueprint.emotional_arc }}
              </span>
            </div>
            <h4 class="text-sm font-bold text-slate-900 truncate">
              {{ activeBlueprint.title }}
            </h4>
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <button
            type="button"
            @click="showBlueprintDetails = !showBlueprintDetails"
            class="text-xs font-semibold px-3 py-1.5 rounded-xl border border-amber-200 bg-white/90 hover:bg-white text-amber-900 transition-all shadow-2xs cursor-pointer flex items-center gap-1 active:scale-95"
          >
            <span>{{ showBlueprintDetails ? '收起骨架结构' : '展开骨架结构' }}</span>
            <span class="text-[10px]">{{ showBlueprintDetails ? '▲' : '▼' }}</span>
          </button>
          <button
            type="button"
            @click="clearBlueprint"
            class="text-xs font-semibold px-3 py-1.5 rounded-xl border border-amber-300/80 bg-white/80 hover:bg-amber-100 text-amber-800 transition shadow-2xs cursor-pointer active:scale-95"
          >
            ✕ 清除骨架约束
          </button>
        </div>
      </div>

      <!-- Expandable Blueprint Structure Details -->
      <div
        v-if="showBlueprintDetails"
        class="px-5 pb-5 pt-2 border-t border-amber-200/60 bg-white/40 space-y-3 text-xs"
      >
        <div class="flex flex-wrap items-center gap-3 text-slate-700">
          <span v-if="activeBlueprint.pacing" class="inline-flex items-center gap-1 bg-amber-100/60 px-2 py-1 rounded text-amber-900 font-medium">
            <strong>⏱️ 节奏律动:</strong> {{ activeBlueprint.pacing }}
          </span>
          <span v-if="activeBlueprint.word_count" class="inline-flex items-center gap-1 bg-amber-100/60 px-2 py-1 rounded text-amber-900 font-medium">
            <strong>📏 基准字数:</strong> ~{{ activeBlueprint.word_count }} 字
          </span>
          <span v-if="activeBlueprint.clash_points_count" class="inline-flex items-center gap-1 bg-amber-100/60 px-2 py-1 rounded text-amber-900 font-medium">
            <strong>⚡ 认知冲突点:</strong> {{ activeBlueprint.clash_points_count }} 处
          </span>
          <a
            v-if="activeBlueprint.source_url"
            :href="activeBlueprint.source_url"
            target="_blank"
            class="text-blue-600 underline hover:text-blue-800 ml-auto font-medium"
          >
            查看原对标链接 ↗
          </a>
        </div>

        <div v-if="activeBlueprint.structural_stages && activeBlueprint.structural_stages.length > 0" class="space-y-1.5">
          <span class="font-bold text-amber-900">📑 骨架结构脉络：</span>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
            <div
              v-for="(stage, idx) in activeBlueprint.structural_stages"
              :key="idx"
              class="p-2.5 rounded-lg bg-white/80 border border-amber-200/80 space-y-1"
            >
              <div class="font-bold text-slate-800">阶段 {{ idx + 1 }}</div>
              <p class="text-[11px] text-slate-600 leading-snug">{{ stage }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Reference Material & Lineage Indicator Banner -->
    <div
      v-if="activeMaterial"
      class="max-w-4xl mx-auto rounded-2xl bg-gradient-to-r from-blue-500/10 via-sky-500/5 to-indigo-500/10 glass-card border border-blue-300/70 shadow-xs overflow-hidden transition-all duration-300 scroll-reveal"
    >
      <div class="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3.5 min-w-0">
          <div class="w-10 h-10 rounded-xl bg-blue-500/20 text-blue-900 border border-blue-300/80 flex items-center justify-center text-xl shrink-0 shadow-2xs">
            📌
          </div>
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="inline-flex items-center gap-1.5 text-xs font-black uppercase px-2.5 py-0.5 rounded-full bg-blue-200/90 text-blue-900 border border-blue-300/80 shadow-2xs">
                <span>📌 溯源素材关联</span>
              </span>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-blue-100/80 text-blue-800 border border-blue-200">
                来源平台: [{{ activeMaterial.source_platform || 'web' }}]
              </span>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-blue-100/80 text-blue-800 border border-blue-200">
                作者: [{{ activeMaterial.source_author || '本人' }}]
              </span>
            </div>
            <div class="flex items-center gap-2">
              <h4 class="text-sm font-bold text-slate-900 truncate">
                {{ activeMaterial.title }}
              </h4>
              <a
                v-if="activeMaterial.source_url"
                :href="activeMaterial.source_url"
                target="_blank"
                class="text-xs text-blue-600 underline hover:text-blue-800 shrink-0 font-medium"
              >
                查看原链接 ↗
              </a>
            </div>
          </div>
        </div>

        <button
          type="button"
          @click="clearMaterial"
          class="text-xs font-semibold px-3 py-1.5 rounded-xl border border-blue-300/80 bg-white/90 hover:bg-blue-100 text-blue-800 transition shadow-2xs cursor-pointer active:scale-95 shrink-0"
        >
          {{ t.lineage.clearMaterial }}
        </button>
      </div>
    </div>

    <!-- Closed-Loop DNA Guidance Pill -->
    <div class="max-w-4xl mx-auto flex items-center justify-center scroll-fade">
      <button
        type="button"
        @click="$emit('switch-tab', 'profile')"
        class="group inline-flex items-center gap-2.5 px-4 py-2 rounded-full text-xs font-bold transition-all border shadow-xs cursor-pointer active:scale-95"
        :class="activeTraitsCount > 0 ? 'bg-gradient-to-r from-purple-50 via-indigo-50 to-purple-50 border-purple-200/90 text-purple-900 hover:border-purple-300 hover:shadow-md' : 'bg-slate-100/80 border-slate-200 text-slate-500 hover:bg-slate-200/80'"
      >
        <span class="w-5 h-5 rounded-full bg-purple-600 text-white flex items-center justify-center text-[10px] shadow-2xs group-hover:scale-110 transition">🧬</span>
        <span>{{ activeTraitsCount > 0 ? t.closedLoop.badge.replace('{count}', String(activeTraitsCount)) : t.closedLoop.badgeEmpty }}</span>
        <span class="text-purple-500 group-hover:translate-x-0.5 transition font-mono">→</span>
      </button>
    </div>

    <!-- 4-Step Indicator Tracker (Linear Connected Timeline) -->
    <nav aria-label="Progress" class="max-w-4xl mx-auto scroll-reveal">
      <div class="glass-card rounded-2xl border border-slate-200/80 shadow-xs p-4 sm:p-5">
        <ol class="grid grid-cols-4 items-center gap-2 sm:gap-4 relative">
          <!-- Step 1 -->
          <li class="relative">
            <button

              type="button"
              @click="goToStep(1)"
              :disabled="currentStep === 1"
              class="w-full text-left flex flex-col items-center sm:items-start group transition cursor-pointer disabled:cursor-default"
            >
              <div class="flex items-center gap-2 sm:gap-3 w-full">
                <!-- Step Circle Indicator -->
                <div
                  class="w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0"
                  :class="{
                    'bg-indigo-600 text-white shadow-xs group-hover:bg-indigo-700': currentStep > 1,
                    'relative bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-black shadow-md ring-4 ring-indigo-100': currentStep === 1,
                    'bg-slate-100 border border-slate-200 text-slate-400': currentStep < 1,
                  }"
                >
                  <span v-if="currentStep === 1" class="absolute -inset-1 rounded-full bg-indigo-500/25 animate-ping"></span>
                  <span v-if="currentStep > 1" class="text-white text-sm font-bold">✓</span>
                  <span v-else class="relative z-10">1</span>
                </div>
                <!-- Line to Step 2 -->
                <div
                  class="hidden sm:block flex-1 h-0.5 rounded-full transition-all duration-300"
                  :class="currentStep > 1 ? 'bg-indigo-600' : 'bg-slate-200'"
                ></div>
              </div>
              <div class="mt-2 text-center sm:text-left">
                <span class="block text-[10px] uppercase font-bold tracking-wider" :class="currentStep === 1 ? 'text-indigo-600' : 'text-slate-400'">
                  01 · 灵感确立
                </span>
                <span class="text-xs sm:text-sm font-bold block truncate max-w-[120px] sm:max-w-none" :class="currentStep === 1 ? 'text-slate-900' : currentStep > 1 ? 'text-slate-700' : 'text-slate-400'">
                  {{ activeBlueprint ? (t.blueprint?.step1BoneTitle || '输入骨架新选题') : t.app.step1 }}
                </span>
              </div>
            </button>
          </li>

          <!-- Step 2 -->
          <li class="relative">
            <button
              type="button"
              @click="goToStep(2)"
              :disabled="currentStep === 2 || (!outlines && !activeBlueprint)"
              class="w-full text-left flex flex-col items-center sm:items-start group transition"
              :class="(outlines || activeBlueprint) && currentStep !== 2 ? 'cursor-pointer' : 'cursor-default'"
            >
              <div class="flex items-center gap-2 sm:gap-3 w-full">
                <!-- Step Circle Indicator -->
                <div
                  class="w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0"
                  :class="{
                    'bg-indigo-600 text-white shadow-xs group-hover:bg-indigo-700': currentStep > 2,
                    'relative bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-black shadow-md ring-4 ring-indigo-100': currentStep === 2,
                    'bg-slate-100 border border-slate-200 text-slate-400': currentStep < 2,
                  }"
                >
                  <span v-if="currentStep === 2" class="absolute -inset-1 rounded-full bg-indigo-500/25 animate-ping"></span>
                  <span v-if="currentStep > 2" class="text-white text-sm font-bold">✓</span>
                  <span v-else class="relative z-10">2</span>
                </div>
                <!-- Line to Step 3 -->
                <div
                  class="hidden sm:block flex-1 h-0.5 rounded-full transition-all duration-300"
                  :class="currentStep > 2 ? 'bg-indigo-600' : 'bg-slate-200'"
                ></div>
              </div>
              <div class="mt-2 text-center sm:text-left">
                <span class="block text-[10px] uppercase font-bold tracking-wider" :class="currentStep === 2 ? 'text-indigo-600' : 'text-slate-400'">
                  02 · 视角大纲
                </span>
                <span class="text-xs sm:text-sm font-bold block truncate max-w-[120px] sm:max-w-none" :class="currentStep === 2 ? 'text-slate-900' : currentStep > 2 ? 'text-slate-700' : 'text-slate-400'">
                  {{ activeBlueprint ? (t.blueprint?.step2BoneTitle || '骨架结构注入') : t.app.step2 }}
                </span>
              </div>
            </button>
          </li>

          <!-- Step 3 -->
          <li class="relative">
            <button
              type="button"
              @click="goToStep(3)"
              :disabled="currentStep === 3 || !generatedDraft"
              class="w-full text-left flex flex-col items-center sm:items-start group transition"
              :class="generatedDraft && currentStep !== 3 ? 'cursor-pointer' : 'cursor-default'"
            >
              <div class="flex items-center gap-2 sm:gap-3 w-full">
                <!-- Step Circle Indicator -->
                <div
                  class="w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0"
                  :class="{
                    'bg-indigo-600 text-white shadow-xs group-hover:bg-indigo-700': currentStep > 3,
                    'relative bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-black shadow-md ring-4 ring-indigo-100': currentStep === 3,
                    'bg-slate-100 border border-slate-200 text-slate-400': currentStep < 3,
                  }"
                >
                  <span v-if="currentStep === 3" class="absolute -inset-1 rounded-full bg-indigo-500/25 animate-ping"></span>
                  <span v-if="currentStep > 3" class="text-white text-sm font-bold">✓</span>
                  <span v-else class="relative z-10">3</span>
                </div>
                <!-- Line to Step 4 -->
                <div
                  class="hidden sm:block flex-1 h-0.5 rounded-full transition-all duration-300"
                  :class="currentStep > 3 ? 'bg-violet-600' : 'bg-slate-200'"
                ></div>
              </div>
              <div class="mt-2 text-center sm:text-left">
                <span class="block text-[10px] uppercase font-bold tracking-wider" :class="currentStep === 3 ? 'text-indigo-600' : 'text-slate-400'">
                  03 · 深度精修
                </span>
                <span class="text-xs sm:text-sm font-bold block truncate max-w-[120px] sm:max-w-none" :class="currentStep === 3 ? 'text-slate-900' : currentStep > 3 ? 'text-slate-700' : 'text-slate-400'">
                  {{ t.app.step3 }}
                </span>
              </div>
            </button>
          </li>

          <!-- Step 4 -->
          <li class="relative">
            <button
              type="button"
              @click="goToStep(4)"
              :disabled="currentStep === 4 || !dnaResult"
              class="w-full text-left flex flex-col items-center sm:items-start group transition"
              :class="dnaResult && currentStep !== 4 ? 'cursor-pointer' : 'cursor-default'"
            >
              <div class="flex items-center gap-2 sm:gap-3 w-full">
                <!-- Step Circle Indicator -->
                <div
                  class="w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0"
                  :class="{
                    'relative bg-gradient-to-tr from-purple-600 to-indigo-600 text-white font-black shadow-md ring-4 ring-purple-100': currentStep === 4,
                    'bg-slate-100 border border-slate-200 text-slate-400': currentStep < 4,
                  }"
                >
                  <span v-if="currentStep === 4" class="absolute -inset-1 rounded-full bg-purple-500/25 animate-ping"></span>
                  <span class="relative z-10">4</span>
                </div>
              </div>
              <div class="mt-2 text-center sm:text-left">
                <span class="block text-[10px] uppercase font-bold tracking-wider" :class="currentStep === 4 ? 'text-purple-600' : 'text-slate-400'">
                  04 · 认知沉淀
                </span>
                <span class="text-xs sm:text-sm font-bold block truncate max-w-[120px] sm:max-w-none" :class="currentStep === 4 ? 'text-slate-900' : 'text-slate-400'">
                  {{ t.app.step4 }}
                </span>
              </div>
            </button>
          </li>
        </ol>
      </div>
    </nav>

    <!-- Error Alert -->
    <div
      v-if="errorMessage"
      class="max-w-4xl mx-auto p-4 bg-red-50 border-l-4 border-red-500 rounded-r-xl flex items-start justify-between shadow-2xs"
    >
      <div class="flex items-center space-x-3">
        <svg class="h-5 w-5 text-red-500 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
        <span class="text-sm font-medium text-red-800">{{ errorMessage }}</span>
      </div>
      <button @click="errorMessage = ''" class="text-red-500 hover:text-red-700 text-sm font-bold ml-4 cursor-pointer">
        ✕
      </button>
    </div>

    <!-- Main Creation Steps -->
    <main class="space-y-6">
      <!-- Step 1: Topic Input & IP Memory Asset Tuning -->
      <section v-if="currentStep === 1" class="max-w-4xl mx-auto space-y-5 transition-all duration-300 scroll-reveal">
        <!-- 🎭 IP Persona & Memory Asset Tuning Card (Collapsible Pill/Card) -->
        <div class="rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/90 via-purple-50/50 to-indigo-50/90 glass-card shadow-xs overflow-hidden transition-all duration-300 scroll-reveal">
          <!-- Collapsed / Top Bar Header (Clickable to toggle) -->
          <div
            @click="showTuningDetails = !showTuningDetails"
            class="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4 cursor-pointer select-none hover:bg-white/30 transition"
          >
            <div class="flex items-center gap-3.5 min-w-0">
              <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center text-xl shrink-0 shadow-xs font-bold">
                🎭
              </div>
              <div class="min-w-0 space-y-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="inline-flex items-center gap-1.5 text-xs font-black uppercase px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-900 border border-indigo-300/80 shadow-2xs">
                    <span>{{ t.tuning.cardTitle }}</span>
                  </span>
                  <!-- Active Persona Pill Badge -->
                  <span
                    v-if="currentPersona"
                    class="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full bg-white text-indigo-950 border border-indigo-200 shadow-2xs"
                  >
                    <span>👤 {{ currentPersona.name }}</span>
                    <span class="text-indigo-400">·</span>
                    <span class="text-slate-600 font-normal">「{{ currentPersona.reader_salutation || t.holographic.defaultSalutation }}」</span>
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 shadow-2xs"
                  >
                    <span>👤 {{ t.tuning.personaNeutral }}</span>
                  </span>
                  <!-- Stories Injection Pill Badge -->
                  <span
                    class="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full border shadow-2xs"
                    :class="injectStories ? 'bg-purple-100/90 text-purple-900 border-purple-200' : 'bg-slate-100 text-slate-500 border-slate-200'"
                  >
                    <span>📖 {{ injectStories ? t.tuning.storyInjectionOn : t.tuning.storyInjectionOff }}</span>
                    <span v-if="injectStories && stories.length > 0" class="text-[10px] bg-purple-200/80 px-1.5 py-0.2 rounded-full">
                      {{ t.tuning.storiesReadyBadge.replace('{count}', String(stories.length)) }}
                    </span>
                  </span>
                  <!-- Product Vault Pill Badge -->
                  <span
                    v-if="currentProduct"
                    class="inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 shadow-2xs"
                  >
                    <span>📦 {{ currentProduct.product_name }}</span>
                    <span class="text-[10px] text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded">
                      {{ currentProduct.category }}
                    </span>
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100/80 text-slate-500 border border-slate-200"
                  >
                    <span>{{ t.tuning.productNoneBadge }}</span>
                  </span>
                </div>
                <p class="text-xs text-slate-600 truncate max-w-xl">
                  {{ t.tuning.cardSubtitle }}
                </p>
              </div>
            </div>

            <button
              type="button"
              @click.stop="showTuningDetails = !showTuningDetails"
              class="text-xs font-semibold px-3 py-1.5 rounded-xl border border-indigo-200 bg-white/90 hover:bg-white text-indigo-900 transition-all shadow-2xs cursor-pointer flex items-center gap-1 active:scale-95 shrink-0 ml-auto"
            >
              <span>{{ showTuningDetails ? t.tuning.collapse : t.tuning.expand }}</span>
              <span class="text-[10px]">{{ showTuningDetails ? '▲' : '▼' }}</span>
            </button>
          </div>

          <!-- Expanded Tuning Panels (3 Sections Grid) -->
          <div
            v-if="showTuningDetails"
            class="px-5 pb-5 pt-3 border-t border-indigo-200/60 bg-white/80 space-y-4 text-xs"
          >
            <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
              <!-- 1. Persona Selector (5 Cols) -->
              <div class="md:col-span-5 space-y-2">
                <div class="flex items-center justify-between">
                  <label class="font-bold text-slate-900 flex items-center gap-1.5 text-xs">
                    <span>👤</span>
                    <span>{{ t.tuning.personaLabel }}</span>
                  </label>
                  <span class="text-[10px] text-slate-400">{{ t.tuning.personaHint }}</span>
                </div>

                <div v-if="personas.length === 0" class="p-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-500 text-xs">
                  {{ t.tuning.noPersonaHint }}
                </div>

                <div v-else class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  <!-- Neutral Voice Option -->
                  <div
                    @click="selectedPersonaId = ''"
                    class="p-2.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-0.5 text-left relative"
                    :class="
                      !selectedPersonaId
                        ? 'border-indigo-600 bg-indigo-50/70 shadow-2xs ring-1 ring-indigo-500/20'
                        : 'border-slate-200/70 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                    "
                  >
                    <div class="flex items-center justify-between">
                      <span class="text-xs font-bold text-slate-900 flex items-center gap-1">
                        <span v-if="!selectedPersonaId" class="text-indigo-600 font-bold">✓</span>
                        <span>🍃 {{ t.tuning.personaNeutral }}</span>
                      </span>
                    </div>
                    <p class="text-[11px] text-slate-500">
                      {{ t.tuning.personaNeutralHint }}
                    </p>
                  </div>

                  <!-- Custom Personas -->
                  <div
                    v-for="p in personas"
                    :key="p.id"
                    @click="selectedPersonaId = p.id"
                    class="p-2.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-0.5 text-left relative"
                    :class="
                      selectedPersonaId === p.id
                        ? 'border-indigo-600 bg-indigo-50/70 shadow-2xs ring-1 ring-indigo-500/20'
                        : 'border-slate-200/70 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                    "
                  >
                    <div class="flex items-center justify-between">
                      <span class="text-xs font-bold text-slate-900 flex items-center gap-1">
                        <span v-if="selectedPersonaId === p.id" class="text-indigo-600 font-bold">✓</span>
                        <span>{{ p.name }}</span>
                      </span>
                      <span class="text-[10px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200/60 font-semibold">
                        {{ t.tuning.salutationLabel }}:「{{ p.reader_salutation || t.holographic.defaultSalutation }}」
                      </span>
                    </div>
                    <p class="text-[11px] text-slate-500 line-clamp-1">
                      {{ t.tuning.toneLabel }}: {{ p.tone_style || '温暖专业接地气' }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- 2. Episodic Stories Toggle (4 Cols) -->
              <div class="md:col-span-4 space-y-2">
                <div class="flex items-center justify-between">
                  <label class="font-bold text-slate-900 flex items-center gap-1.5 text-xs">
                    <span>📖</span>
                    <span>{{ t.tuning.storiesSectionTitle }}</span>
                  </label>
                  <label class="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      v-model="injectStories"
                      class="sr-only peer"
                    />
                    <div class="w-8 h-4 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-purple-600"></div>
                  </label>
                </div>

                <div class="p-3 rounded-xl border border-purple-200/80 bg-purple-50/40 space-y-2">
                  <p class="text-[11px] text-purple-900 leading-relaxed">
                    {{ t.tuning.storyToggleDesc }}
                  </p>

                  <div v-if="injectStories" class="space-y-1.5 pt-1 border-t border-purple-200/50">
                    <div class="flex items-center justify-between text-[11px]">
                      <span class="font-semibold text-purple-800">
                        {{ t.tuning.storiesReady.replace('{count}', String(stories.length)) }}
                      </span>
                      <span class="text-[10px] text-purple-600 bg-purple-100 px-1.5 py-0.2 rounded-full font-medium">
                        {{ t.tuning.autoMatchPill }}
                      </span>
                    </div>
                    <div class="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                      <span
                        v-for="st in stories"
                        :key="st.id"
                        class="px-2 py-0.5 rounded-lg text-[10px] font-medium bg-white text-purple-800 border border-purple-200/80 shadow-2xs truncate max-w-[140px]"
                        :title="`${st.title} (${st.occurred_at || '日常经历'})`"
                      >
                        {{ st.title }}
                      </span>
                      <span v-if="stories.length === 0" class="text-[10px] text-purple-600 italic">
                        {{ t.tuning.noStoriesHint }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 3. Product Vault Selector (3 Cols) -->
              <div class="md:col-span-3 space-y-2">
                <div class="flex items-center justify-between">
                  <label class="font-bold text-slate-900 flex items-center gap-1.5 text-xs">
                    <span>📦</span>
                    <span>{{ t.tuning.productBadge }}</span>
                  </label>
                  <span class="text-[10px] text-slate-400">{{ t.tuning.productOptional }}</span>
                </div>

                <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  <!-- None Option -->
                  <div
                    @click="selectedProductId = ''"
                    class="p-2 rounded-xl border text-xs font-semibold cursor-pointer transition text-left"
                    :class="
                      !selectedProductId
                        ? 'border-slate-800 bg-slate-900 text-white'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                    "
                  >
                    {{ t.tuning.productNone }}
                  </div>

                  <!-- Product Options -->
                  <div
                    v-for="prod in products"
                    :key="prod.id"
                    @click="selectedProductId = prod.id"
                    class="p-2 rounded-xl border transition-all cursor-pointer flex flex-col gap-0.5 text-left"
                    :class="
                      selectedProductId === prod.id
                        ? 'border-amber-600 bg-amber-50/70 shadow-2xs ring-1 ring-amber-500/20'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                    "
                  >
                    <div class="flex items-center justify-between">
                      <span class="text-xs font-bold text-slate-900 truncate">
                        {{ prod.product_name }}
                      </span>
                      <span class="text-[9px] text-amber-700 bg-amber-100 px-1 py-0.2 rounded shrink-0">
                        {{ prod.category }}
                      </span>
                    </div>
                    <p class="text-[10px] text-slate-500 line-clamp-1">
                      {{ prod.suitable_conditions || prod.personal_usage_experience }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <TopicInput
          :loading="isGeneratingOutlines || isGeneratingBlueprintDraft"
          :initial-topic="currentTopic"
          :initial-context="currentContext"
          @submit="handleTopicSubmit"
          @open-deconstruct="showDeconstructModal = true"
        />
      </section>

      <!-- Step 2: Outline Selection (for standard non-blueprint flow) -->
      <section v-if="currentStep === 2 && outlines" class="space-y-4 transition-all duration-300 scroll-reveal">
        <div class="max-w-6xl mx-auto flex items-center justify-between px-2 flex-wrap gap-2">
          <div>
            <span class="text-xs uppercase tracking-wider text-slate-400 font-semibold">{{ locale === 'zh' ? '当前创作选题：' : 'Active Topic:' }}</span>
            <div class="flex items-center gap-3 flex-wrap">
              <h3 class="text-lg font-bold text-slate-800">{{ currentTopic }}</h3>
              <!-- Mini Context Badges showing active tuning -->
              <div class="flex items-center gap-1.5 text-xs flex-wrap">
                <span class="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-800 border border-indigo-200 text-[11px] font-medium">
                  🎭 {{ currentPersona ? currentPersona.name : t.tuning.personaNeutral }}
                </span>
                <span
                  class="px-2 py-0.5 rounded-full text-[11px] font-medium border"
                  :class="injectStories ? 'bg-purple-50 text-purple-800 border-purple-200' : 'bg-slate-50 text-slate-500 border-slate-200'"
                >
                  📖 {{ injectStories ? t.tuning.step2StoriesInjected : t.tuning.step2NoStories }}
                </span>
                <span class="px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-medium">
                  📦 {{ currentProduct ? currentProduct.product_name : t.tuning.step2PurePerspective }}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            @click="currentStep = 1"
            class="text-sm text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
          >
            {{ locale === 'zh' ? '← 更换选题' : '← Edit Topic' }}
          </button>
        </div>

        <DraftSelection
          :draft-a="adaptedDraftA"
          :draft-b="adaptedDraftB"
          :initial-selected="selectedOption"
          :loading="isGeneratingDraft"
          @confirm="handleOutlineSelect"
        />
      </section>

      <!-- Step 3: Draft Editor & Diff -->
      <section v-if="currentStep === 3 && generatedDraft" class="max-w-4xl mx-auto space-y-6 transition-all duration-300 scroll-reveal">
        <DraftEditor
          :draft-id="currentDraftId"
          :blueprint-title="activeBlueprint?.title"
          :blueprint-id="activeBlueprint?.id"
          :source-material="activeMaterial"
          :lineage-snapshot="generatedDraft.lineage_snapshot"
          :original-draft="generatedDraft.content"
          :initial-edited-draft="currentEditedDraft"
          :title="generatedDraft.title"
          :summary="generatedDraft.summary"
          :topic="currentTopic"
          :core-viewpoints="generatedDraft.core_viewpoints"
          :active-persona="generatedDraft?.persona || currentPersona"
          :active-product="generatedDraft?.product || currentProduct"
          :bound-stories="generatedDraft?.stories || currentBoundStories"
          :persona-id="generatedDraft?.persona_id || selectedPersonaId"
          :product-id="generatedDraft?.product_id || selectedProductId"
          :story-ids="generatedDraft?.story_ids || (injectStories ? currentBoundStories.map(s => s.id) : [])"
          :loading="isExtractingDNA"
          @update:draft-id="(id: string) => (currentDraftId = id)"
          @update:edited-draft="(val: string) => (currentEditedDraft = val)"
          @extract-dna="handleExtractDNA"
          @extract-d-n-a="handleExtractDNA"
          @back-to-outlines="currentStep = activeBlueprint ? 1 : 2"
        />
      </section>

      <!-- Step 4: Thinking DNA Results -->
      <section v-if="currentStep === 4 && dnaResult" class="transition-all duration-300 scroll-reveal">
        <DNAResult
          :dna-output="dnaResult"
          :topic="currentTopic"
          @re-edit-draft="currentStep = 3"
          @new-topic="resetWorkflow"
          @distribute="showWorkbenchDistributeModal = true"
          @open-feedback="showWorkbenchFeedbackModal = true"
        />
      </section>

      <!-- Benchmark Deconstruction Modal (Module 4) -->
      <BenchmarkDeconstructModal
        :show="showDeconstructModal"
        @close="showDeconstructModal = false"
        @update:show="(val: boolean) => (showDeconstructModal = val)"
        @create-with-blueprint="handleCreateWithBlueprint"
      />

      <!-- Multi-Platform Distribution Modal (accessible across Workbench) -->
      <MultiPlatformDistributeModal
        :show="showWorkbenchDistributeModal"
        :content="currentEditedDraft || generatedDraft?.content"
        :title="generatedDraft?.title || currentTopic"
        :draft-id="dnaResult?.draft_id"
        @close="showWorkbenchDistributeModal = false"
        @update:show="(val: boolean) => (showWorkbenchDistributeModal = val)"
      />

      <!-- Audience Feedback & Evolution Modal (Phase 4 accessible directly from Workbench) -->
      <FeedbackModal
        v-if="showWorkbenchFeedbackModal && (currentDraftId || dnaResult?.draft_id)"
        :draft-id="currentDraftId || dnaResult?.draft_id || ''"
        :draft-topic="currentTopic"
        @close="showWorkbenchFeedbackModal = false"
        @dna-evolved="emit('dna-updated')"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from '../i18n'
import TopicInput from './TopicInput.vue'
import DraftSelection from './DraftSelection.vue'
import DraftEditor from './DraftEditor.vue'
import DNAResult from './DNAResult.vue'
import MultiPlatformDistributeModal from './MultiPlatformDistributeModal.vue'
import BenchmarkDeconstructModal from './BenchmarkDeconstructModal.vue'
import FeedbackModal from './FeedbackModal.vue'
import type { HistoryDraftItem } from '../services/historyStorage'
import type { Draft } from './DraftSelection.vue'
import {
  generateOutlines,
  generateDraft,
  generateDraftFromBlueprint,
  extractThinkingDNA,
  fetchPersonas,
  fetchProducts,
  fetchStories,
  type OutlineOutput,
  type Outline,
  type DraftOutput,
  type DNAExtractionOutput,
  type ViewpointJudgment,
  type BenchmarkBlueprint,
  type Material,
  type IPPersona,
  type ProductVaultItem,
  type EpisodicStoryItem,
} from '../services/api'

const { t, locale } = useI18n()

const props = withDefaults(
  defineProps<{
    initialBlueprint?: BenchmarkBlueprint | null
    activeTraitsCount?: number
  }>(),
  {
    initialBlueprint: null,
    activeTraitsCount: 0,
  }
)

const emit = defineEmits<{
  (e: 'switch-tab', tab: string): void
  (e: 'dna-updated'): void
}>()

const activeBlueprint = ref<BenchmarkBlueprint | null>(props.initialBlueprint || null)
const activeMaterial = ref<Material | null>(null)
const showBlueprintDetails = ref(false)

watch(
  () => props.initialBlueprint,
  (bp) => {
    if (bp && !activeBlueprint.value) {
      activeBlueprint.value = bp
      if (currentStep.value < 3) {
        currentStep.value = 1
      }
    }
  }
)

function clearBlueprint() {
  activeBlueprint.value = null
  showBlueprintDetails.value = false
}

function clearMaterial() {
  activeMaterial.value = null
}

function loadMaterial(
  mat: Material,
  topic?: string,
  blueprint?: BenchmarkBlueprint,
  context?: string
) {
  currentDraftId.value = ''
  activeMaterial.value = mat
  const rawBp = blueprint || mat.blueprint_data
  if (rawBp) {
    activeBlueprint.value = {
      id: (rawBp as any).id || mat.id,
      title: (rawBp as any).title || mat.title || '对标爆款骨架',
      ...rawBp,
    } as any
  } else {
    activeBlueprint.value = null
  }
  currentTopic.value = topic || mat.title
  currentContext.value = context
  currentStep.value = 1
}

// IP Persona & Memory Tuning State
const personas = ref<IPPersona[]>([])
const selectedPersonaId = ref<string>('')
const products = ref<ProductVaultItem[]>([])
const selectedProductId = ref<string>('')
const stories = ref<EpisodicStoryItem[]>([])
const injectStories = ref<boolean>(true)
const showTuningDetails = ref<boolean>(false)

const currentPersona = computed(() => {
  if (!selectedPersonaId.value) return null
  return personas.value.find(p => p.id === selectedPersonaId.value) || null
})

const currentProduct = computed(() => {
  return products.value.find(p => p.id === selectedProductId.value) || null
})

const currentBoundStories = computed(() => {
  if (!injectStories.value) return []
  return stories.value
})

// 4-Step Workflow State
const currentStep = ref<1 | 2 | 3 | 4>(1)
const currentTopic = ref('')
const currentContext = ref<string | undefined>(undefined)

function goToStep(step: 1 | 2 | 3 | 4) {
  if (step === currentStep.value) return
  if (step === 1) {
    currentStep.value = 1
  } else if (step === 2 && (outlines.value || activeBlueprint.value)) {
    currentStep.value = 2
  } else if (step === 3 && generatedDraft.value) {
    currentStep.value = 3
  } else if (step === 4 && dnaResult.value) {
    currentStep.value = 4
  }
}

// Agent Outputs
const outlines = ref<OutlineOutput | null>(null)
const selectedOption = ref<'A' | 'B'>('A')
const generatedDraft = ref<DraftOutput | null>(null)
const currentEditedDraft = ref('')
const currentDraftId = ref('')
const dnaResult = ref<DNAExtractionOutput | null>(null)

// Loading & UI States
const isGeneratingOutlines = ref(false)
const isGeneratingDraft = ref(false)
const isGeneratingBlueprintDraft = ref(false)
const isExtractingDNA = ref(false)
const showWorkbenchDistributeModal = ref(false)
const showDeconstructModal = ref(false)
const showWorkbenchFeedbackModal = ref(false)

function handleCreateWithBlueprint(payload: { blueprint: BenchmarkBlueprint }) {
  activeBlueprint.value = payload.blueprint
  currentStep.value = 1
}

function loadDraft(draft: HistoryDraftItem) {
  currentDraftId.value = draft.id
  currentTopic.value = draft.topic
  generatedDraft.value = {
    title: draft.topic,
    content: draft.original_draft || draft.content,
    summary: draft.summary,
    lineage_snapshot: draft.lineage_snapshot,
    persona_id: draft.lineage_snapshot?.persona_id,
    product_id: draft.lineage_snapshot?.product_id,
    story_ids: draft.lineage_snapshot?.story_ids,
  }
  if (draft.lineage_snapshot?.persona_id) {
    selectedPersonaId.value = draft.lineage_snapshot.persona_id
  }
  if (draft.lineage_snapshot?.product_id !== undefined) {
    selectedProductId.value = draft.lineage_snapshot.product_id || ''
  }
  if (draft.lineage_snapshot?.story_ids) {
    injectStories.value = draft.lineage_snapshot.story_ids.length > 0
  }
  currentEditedDraft.value = draft.content
  currentStep.value = 3
}
const errorMessage = ref('')

// Adapters from backend Outline to DraftSelection format
const adaptedDraftA = computed<Draft>(() => {
  if (!outlines.value?.outline_a) {
    return {
      title: locale.value === 'zh' ? '方案 A（正向逻辑线）' : 'Analytical & Direct',
      summary: locale.value === 'zh' ? '结构严谨、数据导向与逐层推导的分析式框架。' : 'A structured, logic-first approach focusing on data and clear arguments.',
      structure: locale.value === 'zh' ? ['引入背景', '核心论点推导', '案例与实证', '总结与行动'] : ['Introduction', 'Core Arguments', 'Case Evidence', 'Conclusion'],
    }
  }
  const o = outlines.value.outline_a
  return {
    title: o.title,
    summary: o.rationale,
    structure: o.sections.map((s) =>
      s.bullet_points.length > 0 ? `${s.title}: ${s.bullet_points.join(' · ')}` : s.title
    ),
  }
})

const adaptedDraftB = computed<Draft>(() => {
  if (!outlines.value?.outline_b) {
    return {
      title: locale.value === 'zh' ? '方案 B（逆向侧翼视角）' : 'Narrative & Contrarian',
      summary: locale.value === 'zh' ? '叙事驱动、冲突张力与反直觉视角的洞察线索。' : 'A lateral, story-driven perspective exploring counter-intuitive angles.',
      structure: locale.value === 'zh' ? ['开篇钩子', '张力与困境', '认知反转', '升华综合'] : ['The Hook', 'Tension & Stakes', 'The Pivot', 'Synthesis'],
    }
  }
  const o = outlines.value.outline_b
  return {
    title: o.title,
    summary: o.rationale,
    structure: o.sections.map((s) =>
      s.bullet_points.length > 0 ? `${s.title}: ${s.bullet_points.join(' · ')}` : s.title
    ),
  }
})

// Step 1: Submit Topic
const handleTopicSubmit = async (payload: { topic: string; additionalContext?: string }) => {
  errorMessage.value = ''
  currentTopic.value = payload.topic
  currentContext.value = payload.additionalContext

  const storyIds = injectStories.value && stories.value.length > 0 ? stories.value.map(s => s.id) : undefined

  // If blueprint is loaded, generate full draft directly using bone & skin!
  if (activeBlueprint.value) {
    isGeneratingBlueprintDraft.value = true
    try {
      const draftResult = await generateDraftFromBlueprint({
        topic: payload.topic,
        blueprint_id: activeBlueprint.value.id,
        blueprint: activeBlueprint.value,
        additional_context: payload.additionalContext,
        source_material_id: activeMaterial.value?.id,
        persona_id: selectedPersonaId.value || undefined,
        product_id: selectedProductId.value || undefined,
        story_ids: storyIds,
      })
      generatedDraft.value = draftResult
      currentDraftId.value = draftResult.id || draftResult.draft_id || ''
      currentEditedDraft.value = draftResult.content
      currentStep.value = 3
    } catch (err: any) {
      errorMessage.value = err.message || 'Failed to generate draft from blueprint.'
    } finally {
      isGeneratingBlueprintDraft.value = false
    }
    return
  }

  // Standard flow: explore divergent outlines
  isGeneratingOutlines.value = true
  try {
    const result = await generateOutlines(
      payload.topic,
      payload.additionalContext,
      selectedPersonaId.value || undefined,
      selectedProductId.value || undefined,
      storyIds
    )
    outlines.value = result
    currentStep.value = 2
  } catch (err: any) {
    errorMessage.value = err.message || 'Failed to generate outlines. Please check server.'
  } finally {
    isGeneratingOutlines.value = false
  }
}

// Step 2: Confirm Outline to Draft Generation Agent
const handleOutlineSelect = async (selection: string) => {
  if (!outlines.value) return
  errorMessage.value = ''
  isGeneratingDraft.value = true
  selectedOption.value = selection === 'B' ? 'B' : 'A'

  const chosenOutline: Outline =
    selectedOption.value === 'A' ? outlines.value.outline_a : outlines.value.outline_b

  const storyIds = injectStories.value && stories.value.length > 0 ? stories.value.map(s => s.id) : undefined
  try {
    const draftResult = await generateDraft(
      currentTopic.value,
      chosenOutline,
      currentContext.value,
      activeMaterial.value?.id,
      activeBlueprint.value?.id,
      selectedPersonaId.value || undefined,
      selectedProductId.value || undefined,
      storyIds
    )
    generatedDraft.value = draftResult
    currentDraftId.value = draftResult.id || draftResult.draft_id || ''
    currentEditedDraft.value = draftResult.content
    currentStep.value = 3
  } catch (err: any) {
    errorMessage.value = err.message || 'Failed to generate article draft. Please try again.'
  } finally {
    isGeneratingDraft.value = false
  }
}

// Step 3: Extract Thinking DNA from edits
const handleExtractDNA = async (payload: {
  originalDraft: string
  userEditedDraft: string
  viewpointJudgments?: ViewpointJudgment[]
}) => {
  errorMessage.value = ''
  isExtractingDNA.value = true
  currentEditedDraft.value = payload.userEditedDraft

  try {
    const result = await extractThinkingDNA({
      original_ai_draft: payload.originalDraft,
      user_final_draft: payload.userEditedDraft,
      topic: currentTopic.value,
      draft_id: dnaResult.value?.draft_id,
      viewpoint_judgments: payload.viewpointJudgments,
    })
    dnaResult.value = result
    currentStep.value = 4
    emit('dna-updated')
  } catch (err: any) {
    errorMessage.value = err.message || 'Failed to extract Thinking DNA. Please try again.'
  } finally {
    isExtractingDNA.value = false
  }
}

const resetWorkflow = () => {
  currentStep.value = 1
  currentTopic.value = ''
  currentContext.value = undefined
  outlines.value = null
  generatedDraft.value = null
  currentEditedDraft.value = ''
  currentDraftId.value = ''
  dnaResult.value = null
  errorMessage.value = ''
}

function loadBlueprint(
  bp: BenchmarkBlueprint,
  draftResult?: DraftOutput,
  topic?: string,
  context?: string
) {
  activeBlueprint.value = bp
  if (draftResult) {
    currentTopic.value = topic || bp.title
    currentContext.value = context
    generatedDraft.value = draftResult
    currentEditedDraft.value = draftResult.content
    currentStep.value = 3
  } else {
    currentTopic.value = topic || ''
    currentContext.value = context
    currentStep.value = 1
  }
}

onMounted(async () => {
  try {
    const [fetchedPersonas, fetchedProducts, fetchedStories] = await Promise.all([
      fetchPersonas().catch(() => []),
      fetchProducts().catch(() => []),
      fetchStories().catch(() => []),
    ])
    personas.value = fetchedPersonas
    if (fetchedPersonas.length > 0) {
      const active = fetchedPersonas.find(p => p.is_active)
      selectedPersonaId.value = active ? active.id : fetchedPersonas[0].id
    }
    products.value = fetchedProducts
    stories.value = fetchedStories
  } catch (e) {
    console.error('Failed to load initial memory tuning assets:', e)
  }

  const params = new URLSearchParams(window.location.search)
  if (params.get('modal') === 'deconstruct') {
    showDeconstructModal.value = true
  }
  if (params.get('step') === '3' && !generatedDraft.value) {
    currentTopic.value = '独立开发者的超级个体跃迁模型'
    generatedDraft.value = {
      title: '独立开发者的超级个体跃迁模型',
      content: '真正拉开超级个体差距的，从来不是代码产出效率，而是认知杠杆的复合积累。坚持长期主义，拒绝低效内卷与无效勤奋，在行动中穿透迷雾，直击本质。\n\n我们要用第一性原理拆解商业命题，形成正向现金流。',
      summary: '探讨独立开发者的思考模式与认知基因。',
    }
    currentEditedDraft.value = generatedDraft.value.content
    currentStep.value = 3
  }
})

function setTopic(topic: string) {
  currentTopic.value = topic
  activeBlueprint.value = null
  activeMaterial.value = null
  currentStep.value = 1
}

defineExpose({
  loadMaterial,
  loadBlueprint,
  loadDraft,
  setTopic,
  resetWorkflow,
})
</script>
