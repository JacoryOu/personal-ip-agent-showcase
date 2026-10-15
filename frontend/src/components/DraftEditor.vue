<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-200/80 overflow-hidden scroll-reveal">
    <!-- Header Bar -->
    <div class="border-b border-slate-200/80 glass-card p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <div class="flex items-center space-x-2 flex-wrap gap-y-1">
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
            {{ t.editor.title }}
          </span>
          <span
            v-if="hasDiff"
            class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800"
          >
            <span>● {{ t.editor.diffTab }}</span>
            <span class="text-xs font-mono">(+{{ addedLinesCount }} / -{{ removedLinesCount }})</span>
          </span>
          <span
            v-else
            class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600"
          >
            {{ t.editor.originalTab }}
          </span>
          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200/60 transition-all duration-300">
            <span>📝 ~{{ currentWordCount }} {{ t.editor.words }}</span>
            <span class="text-slate-300">·</span>
            <span>⏱️ {{ t.holographic.readMinutes.replace('{minutes}', String(readingMinutes)) }}</span>
          </span>
        </div>
        <h2 class="text-2xl font-black text-slate-900 mt-2 tracking-tight">{{ title }}</h2>

        <!-- Lineage Reference Banner -->
        <div
          v-if="sourceMaterial || (lineageSnapshot && lineageSnapshot.source_title)"
          class="mt-2.5 py-1.5 px-3 rounded-xl bg-blue-50/90 border border-blue-200/80 flex flex-wrap items-center justify-between text-xs text-blue-950 gap-2 shadow-2xs"
        >
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-sm">📌</span>
            <span class="font-bold text-blue-900">{{ t.lineage.referredFrom }}</span>
            <span class="font-semibold text-slate-800">{{ sourceMaterial?.title || lineageSnapshot?.source_title }}</span>
            <span class="text-blue-700 text-[11px] bg-blue-100/80 px-1.5 py-0.5 rounded">[{{ sourceMaterial?.source_platform || lineageSnapshot?.source_platform || 'web' }}]</span>
            <span v-if="sourceMaterial?.source_author || lineageSnapshot?.source_author" class="text-blue-700 text-[11px]">by [{{ sourceMaterial?.source_author || lineageSnapshot?.source_author }}]</span>
          </div>
          <a
            v-if="sourceMaterial?.source_url || lineageSnapshot?.source_url"
            :href="sourceMaterial?.source_url || lineageSnapshot?.source_url"
            target="_blank"
            class="text-blue-600 underline hover:text-blue-800 text-[11px] font-semibold"
          >
            {{ t.holographic.viewOriginalMaterial }}
          </a>
        </div>
      </div>

      <!-- Mode & Action Toolbar -->
      <div class="flex items-center space-x-2.5 flex-wrap gap-y-2">
        <!-- View Mode Switcher -->
        <div class="inline-flex rounded-xl border border-slate-200/90 p-1 bg-slate-100/80 text-xs font-medium text-slate-600 shadow-2xs">
          <button
            type="button"
            @click="activeView = 'edit'"
            class="px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 cursor-pointer"
            :class="activeView === 'edit' ? 'bg-white text-indigo-600 shadow-xs font-bold' : 'hover:text-slate-900'"
          >
            <span>✏️ {{ t.editor.editTab }}</span>
          </button>
          <button
            type="button"
            @click="activeView = 'diff'"
            class="px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 cursor-pointer"
            :class="activeView === 'diff' ? 'bg-white text-indigo-600 shadow-xs font-bold' : 'hover:text-slate-900'"
          >
            <span>🔍 {{ t.editor.diffTab }}</span>
          </button>
          <button
            type="button"
            @click="activeView = 'preview'"
            class="px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 cursor-pointer"
            :class="activeView === 'preview' ? 'bg-white text-indigo-600 shadow-xs font-bold' : 'hover:text-slate-900'"
          >
            <span>📖 {{ t.editor.originalTab }}</span>
          </button>
        </div>

        <!-- Discard Changes -->
        <button
          v-if="hasDiff"
          type="button"
          @click="resetToOriginal"
          class="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 shadow-2xs transition-all cursor-pointer active:scale-95"
          :title="locale === 'zh' ? '放弃修改并恢复 AI 原始初稿' : 'Discard user modifications and restore AI original'"
        >
          {{ t.editor.restoreBtn }}
        </button>

        <!-- Save to History Archive (Module 1 feature) -->
        <button
          type="button"
          @click="handleSaveToHistory"
          :disabled="isSavingArchive"
          class="px-3 py-1.5 text-xs font-semibold rounded-xl border shadow-2xs transition-all flex items-center space-x-1.5 cursor-pointer active:scale-95"
          :class="savedArchiveSuccess ? 'border-emerald-300 bg-emerald-50 text-emerald-700' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'"
          title="Save draft into Creation History Archive"
        >
          <span>{{ savedArchiveSuccess ? '✓' : '💾' }}</span>
          <span>{{ savedArchiveSuccess ? (locale === 'zh' ? '已归档' : 'Saved') : (locale === 'zh' ? '存入历史库' : 'Save Draft') }}</span>
        </button>

        <!-- Copy Draft with Keyboard Shortcut Hint -->
        <button
          type="button"
          @click="copyCurrentDraft"
          class="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 shadow-2xs transition-all flex items-center gap-1 cursor-pointer active:scale-95"
          title="复制全文内容 (快捷键: Ctrl+C)"
        >
          <span>{{ copied ? '✓' : '📋' }}</span>
          <span>{{ copied ? t.editor.copiedBtn : t.editor.copyAll }}</span>
          <span class="text-[10px] text-slate-400 font-mono hidden sm:inline">(Ctrl+C)</span>
        </button>

        <!-- Distribute Button -->
        <button
          type="button"
          @click="showDistributeModal = true"
          class="px-3.5 py-1.5 text-xs font-bold rounded-xl border border-indigo-200 bg-indigo-50/80 text-indigo-700 hover:bg-indigo-100 shadow-2xs transition-all flex items-center space-x-1.5 cursor-pointer active:scale-95"
        >
          <span>🐟</span>
          <span>{{ t.distribute.button }}</span>
        </button>

        <!-- Primary CTA: Extract Thinking DNA -->
        <button
          type="button"
          @click="triggerExtraction"
          :disabled="loading || !userEditedDraft.trim()"
          class="px-4 py-2 text-sm font-bold rounded-xl text-white shadow-md transition-all flex items-center space-x-2 cursor-pointer active:scale-95"
          :class="loading || !userEditedDraft.trim()
            ? 'bg-purple-400 cursor-not-allowed'
            : 'bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:from-purple-700 hover:to-indigo-700'"
        >
          <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span v-else>🧬</span>
          <span>{{ loading ? t.editor.extracting : t.editor.extractBtn }}</span>
        </button>
      </div>
    </div>

    <!-- Summary Box (if present) -->
    <div v-if="summary" class="p-4 bg-indigo-50/40 border-b border-indigo-100/60 flex items-start space-x-3">
      <span class="text-indigo-600 font-bold text-sm mt-0.5">💡</span>
      <div class="text-xs text-slate-700 leading-relaxed">
        <strong class="font-semibold text-indigo-900">{{ t.editor.originalAiSummary }}</strong> {{ summary }}
      </div>
    </div>

    <!-- MODULE 2: Holographic IP Memory Board (全息 IP 记忆资产生效看板) -->
    <div class="border-b border-purple-200/70 bg-gradient-to-r from-violet-50/80 via-purple-50/50 to-indigo-50/80 glass-card p-4 sm:p-5 transition-all scroll-reveal">

      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-white flex items-center justify-center text-base shadow-xs font-bold shrink-0 ring-2 ring-purple-200">
            🔮
          </div>
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <h4 class="text-xs font-black text-purple-950 uppercase tracking-wide flex items-center gap-1.5">
                <span>{{ t.holographic.title }}</span>
                <span class="text-[10px] text-purple-600 bg-purple-100 px-2 py-0.5 rounded-full font-mono font-semibold">
                  Thinking DNA 2.0 × IP Persona
                </span>
              </h4>
              <!-- Live Pillar Badges in Top Bar -->
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-purple-200/90 text-purple-900 border border-purple-300/80 shadow-2xs">
                <span>{{ activeTraits.length > 0 ? t.holographic.activeRulesBadge.replace('{count}', String(activeTraits.length)) : t.holographic.noActiveDna }}</span>
                <span v-if="hitCount > 0" class="inline-flex items-center gap-1 text-emerald-800 font-black ml-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse"></span>
                  <span>{{ t.holographic.hitsBadge.replace('{count}', String(hitCount)) }}</span>
                </span>
              </span>
              <!-- Persona Badge in Bar -->
              <span
                v-if="currentPersona"
                class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-900 border border-indigo-200 shadow-2xs"
              >
                <span>🎭 {{ currentPersona.name }}</span>
                <span class="text-indigo-400">·</span>
                <span class="text-indigo-700">「{{ currentPersona.reader_salutation || t.holographic.defaultSalutation }}」</span>
              </span>
              <span
                v-else
                class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200 shadow-2xs"
              >
                <span>🎭 {{ t.holographic.personaEmpty }}</span>
              </span>
              <!-- Stories Badge in Bar -->
              <span
                class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border shadow-2xs"
                :class="currentStories.length > 0 ? 'bg-purple-100 text-purple-900 border-purple-200' : 'bg-slate-100 text-slate-500 border-slate-200'"
              >
                <span>📖 {{ currentStories.length > 0 ? t.holographic.storiesCount.replace('{count}', String(currentStories.length)) : t.holographic.storiesEmpty }}</span>
              </span>
              <!-- Product Badge in Bar (if bound) -->
              <span
                v-if="currentProduct"
                class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200 shadow-2xs"
              >
                <span>📦 {{ currentProduct.product_name }}</span>
              </span>
            </div>
            <p class="text-[11px] text-purple-700/80 mt-0.5">
              {{ t.holographic.subtitle }}
            </p>
          </div>
        </div>

        <button
          type="button"
          @click="showDnaBoard = !showDnaBoard"
          class="text-xs font-bold text-purple-800 hover:text-purple-950 px-3 py-1.5 rounded-xl bg-white/90 border border-purple-200/80 shadow-2xs hover:bg-white transition cursor-pointer flex items-center gap-1 active:scale-95 ml-auto"
        >
          <span>{{ showDnaBoard ? t.holographic.collapse : t.holographic.expand }}</span>
          <span class="text-[10px]">{{ showDnaBoard ? '▲' : '▼' }}</span>
        </button>
      </div>

      <!-- Collapsible Board Body -->
      <div v-if="showDnaBoard" class="mt-4 space-y-4 pt-3.5 border-t border-purple-200/60">
        <!-- 3-Pillar Holographic Status Row (Persona, Stories, Product) -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <!-- Pillar 1: Active IP Persona (发声人设嘴巴) -->
          <div class="p-3.5 rounded-xl bg-white/95 border border-indigo-200/80 shadow-2xs space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-indigo-950 flex items-center gap-1.5">
                <span>🎭</span>
                <span>{{ t.holographic.personaSection }}</span>
              </span>
              <span
                v-if="currentPersona"
                class="text-[10px] font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200/70"
              >
                {{ t.holographic.salutation }}:「{{ currentPersona.reader_salutation || t.holographic.defaultSalutation }}」
              </span>
            </div>
            <div v-if="currentPersona" class="space-y-1 text-xs">
              <h5 class="font-extrabold text-slate-900 text-sm flex items-center gap-1.5">
                {{ currentPersona.name }}
              </h5>
              <div class="flex flex-wrap gap-1 text-[11px] pt-0.5">
                <span class="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-800 font-medium">
                  {{ t.holographic.tone }}: {{ currentPersona.tone_style || '温暖专业接地气' }}
                </span>
                <span v-if="currentPersona.target_audience" class="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                  {{ t.holographic.targetAudience }}: {{ currentPersona.target_audience }}
                </span>
              </div>
              <p v-if="currentPersona.origin_story" class="text-[11px] text-slate-500 italic line-clamp-2 pt-0.5">
                “{{ currentPersona.origin_story }}”
              </p>
            </div>
            <div v-else class="text-xs text-slate-500 italic py-1">
              {{ t.holographic.personaEmpty }}
            </div>
          </div>

          <!-- Pillar 2: Bound Life Stories (融入的个人真实生活切片) -->
          <div class="p-3.5 rounded-xl bg-white/95 border border-purple-200/80 shadow-2xs space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-purple-950 flex items-center gap-1.5">
                <span>📖</span>
                <span>{{ t.holographic.storiesSection }}</span>
              </span>
              <span
                v-if="currentStories.length > 0"
                class="text-[10px] font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200/70"
              >
                {{ t.holographic.storiesCount.replace('{count}', String(currentStories.length)) }}
              </span>
            </div>
            <div v-if="currentStories.length > 0" class="space-y-1.5 text-xs max-h-32 overflow-y-auto pr-1">
              <div
                v-for="st in currentStories"
                :key="st.id"
                class="p-2 rounded-lg bg-purple-50/50 border border-purple-200/60 space-y-1"
              >
                <div class="flex items-center justify-between gap-1 flex-wrap">
                  <span class="font-bold text-purple-950 text-xs truncate">{{ st.title }}</span>
                  <span
                    v-if="st.occurred_at"
                    class="text-[10px] font-semibold text-purple-800 bg-white px-1.5 py-0.2 rounded border border-purple-200 shrink-0"
                  >
                    ⏰ {{ st.occurred_at }}
                  </span>
                </div>
                <p v-if="st.story_content" class="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                  {{ st.story_content }}
                </p>
              </div>
            </div>
            <div v-else class="text-xs text-slate-500 italic py-1 leading-relaxed">
              {{ t.holographic.storiesEmpty }}
            </div>
          </div>

          <!-- Pillar 3: Bound Delivery Solution / Product Vault (挂载的交付方案) -->
          <div class="p-3.5 rounded-xl bg-white/95 border border-amber-200/80 shadow-2xs space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-amber-950 flex items-center gap-1.5">
                <span>📦</span>
                <span>{{ t.holographic.productSection }}</span>
              </span>
              <span
                v-if="currentProduct"
                class="text-[10px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200"
              >
                {{ currentProduct.category }}
              </span>
            </div>
            <div v-if="currentProduct" class="space-y-1.5 text-xs">
              <h5 class="font-extrabold text-slate-900 text-sm">
                {{ currentProduct.product_name }}
              </h5>
              <div v-if="currentProduct.suitable_conditions" class="text-[11px] text-amber-900 bg-amber-50/80 p-1.5 rounded-lg border border-amber-200/60">
                <strong>{{ t.holographic.suitableConditions }}:</strong> {{ currentProduct.suitable_conditions }}
              </div>
              <p v-if="currentProduct.personal_usage_experience" class="text-[11px] text-slate-600 line-clamp-2">
                <strong>{{ t.holographic.usageExperience }}:</strong> {{ currentProduct.personal_usage_experience }}
              </p>
              <div v-if="currentProduct.conversion_hooks" class="text-[11px] text-amber-900 bg-amber-50/80 p-1.5 rounded-lg border border-amber-200/60">
                <strong>{{ t.holographic.conversionHooks }}:</strong> {{ currentProduct.conversion_hooks }}
              </div>
            </div>
            <div v-else class="text-xs text-slate-500 italic py-1">
              {{ t.holographic.productEmpty }}
            </div>
          </div>
        </div>

        <!-- Pillar 4: Thinking DNA 2.0 Matched Cognitive Traits Grid -->
        <div class="space-y-2 pt-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-purple-950 flex items-center gap-1.5">
              <span>🧬</span>
              <span>{{ t.holographic.dnaSection }}</span>
            </span>
            <span class="text-[11px] text-purple-700 font-medium">
              {{ t.holographic.inspectEchoes }}
            </span>
          </div>

          <div v-if="activeTraits.length === 0" class="text-xs text-purple-600/80 py-1 italic bg-white/70 p-3 rounded-xl border border-purple-200/60">
            {{ locale === 'zh' ? '当前系统认知库尚未沉淀特征。本次草稿将基于通识大纲生成，你的润色改动将自动开启 DNA 冷启动！' : 'No cognitive traits active yet. This draft used neutral synthesis; your edits here will cold-start your DNA!' }}
          </div>

          <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            <div
              v-for="trait in activeTraits"
              :key="trait.id"
              class="bg-white/95 border rounded-xl p-3 shadow-2xs space-y-2 transition-all hover:shadow-xs"
              :class="isTraitHit(trait) ? 'border-emerald-300 ring-1 ring-emerald-200/70' : 'border-purple-200/70'"
            >
              <!-- Dimension, Confidence Rating, and Hit Status Badges -->
              <div class="flex items-center justify-between gap-1 flex-wrap">
                <div class="flex items-center gap-1.5">
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
                    :class="dimensionBadgeClass(trait.dimension)"
                  >
                    {{ dimensionLabel(trait.dimension) }}
                  </span>
                  <!-- Confidence Rating Badge -->
                  <span
                    class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200/60"
                    :title="t.holographic.confidenceWeight.replace('{score}', String(trait.confidence_score))"
                  >
                    🎯 {{ t.holographic.confidence }} {{ traitConfidenceLabel(trait.confidence_score) }}
                  </span>
                </div>

                <!-- Live Hit Status Badge -->
                <span
                  v-if="isTraitHit(trait)"
                  class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200"
                  title="This trait has visible echoes or matching vocabulary in the draft content"
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-pulse"></span>
                  <span>{{ t.holographic.liveHit }}</span>
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-100/70 text-purple-700"
                  title="Active as a macro structural or philosophical guideline during generation"
                >
                  <span>{{ t.holographic.prePromptGuide }}</span>
                </span>
              </div>

              <!-- Statement -->
              <p class="text-xs font-semibold text-slate-800 leading-snug break-words">
                {{ trait.statement }}
              </p>
            </div>
          </div>

          <!-- Bottom Explanatory Hint -->
          <div class="text-[11px] text-purple-700/80 flex items-center justify-between flex-wrap gap-2 pt-1">
            <span>💡 {{ t.holographic.hitHint }}</span>
            <span class="text-purple-900 font-semibold bg-purple-100/80 px-2 py-0.5 rounded-full text-[10px]">
              ✨ {{ t.holographic.allFourPillars }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Unmodified Notification / Guidance -->
    <div v-if="!hasDiff && activeView === 'edit'" class="px-6 py-2 bg-amber-50/90 border-b border-amber-200 text-amber-900 text-xs flex items-center justify-between">
      <span>
        ℹ️ <strong>{{ t.editor.tipPrefix }}</strong> {{ t.editor.tipContent }}
      </span>
      <span class="font-mono text-[10px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded">{{ t.editor.originalLoadedBadge }}</span>
    </div>

    <!-- Viewpoint Review Component (Core Claims Review & Stance Injection) -->
    <div v-if="coreViewpoints && coreViewpoints.length > 0" class="px-6 pt-5 pb-1">
      <ViewpointReview
        :viewpoints="coreViewpoints"
        @update:judgments="handleJudgmentsUpdate"
      />
    </div>

    <!-- Main Working Area -->
    <div class="p-5 sm:p-6">
      <!-- 1. Distraction-Free Markdown Editor View -->
      <div v-if="activeView === 'edit'" class="space-y-3">
        <!-- Editor Header & Markdown Formatting Helper Bar -->
        <div class="flex items-center justify-between flex-wrap gap-2">
          <label for="draft-editor-textarea" class="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
            <span>{{ t.editor.editorLabel }}</span>
            <span class="text-[10px] font-normal text-slate-400 font-mono">(支持实时快捷格式)</span>
          </label>

          <!-- Quick Markdown Syntax Insertion Buttons -->
          <div class="inline-flex items-center gap-1 p-0.5 bg-slate-100 rounded-lg text-xs text-slate-600">
            <button
              type="button"
              @click="insertMarkdown('## ', '')"
              class="px-2 py-0.5 hover:bg-white rounded font-bold cursor-pointer transition text-slate-700"
              title="插入二级标题"
            >
              H2
            </button>
            <button
              type="button"
              @click="insertMarkdown('### ', '')"
              class="px-2 py-0.5 hover:bg-white rounded font-bold cursor-pointer transition text-slate-700"
              title="插入三级标题"
            >
              H3
            </button>
            <button
              type="button"
              @click="insertMarkdown('**', '**')"
              class="px-2 py-0.5 hover:bg-white rounded font-bold cursor-pointer transition text-slate-700"
              title="加粗文字"
            >
              B
            </button>
            <button
              type="button"
              @click="insertMarkdown('*', '*')"
              class="px-2 py-0.5 hover:bg-white rounded italic cursor-pointer transition text-slate-700"
              title="斜体文字"
            >
              I
            </button>
            <button
              type="button"
              @click="insertMarkdown('- ', '')"
              class="px-2 py-0.5 hover:bg-white rounded cursor-pointer transition text-slate-700"
              title="列表项"
            >
              • 列表
            </button>
            <button
              type="button"
              @click="insertMarkdown('> ', '')"
              class="px-2 py-0.5 hover:bg-white rounded cursor-pointer transition text-slate-700"
              title="引用段落"
            >
              ” 引用
            </button>
          </div>
        </div>

        <!-- Distraction-free Textarea -->
        <div class="relative rounded-2xl border border-slate-300 focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-100/60 shadow-inner overflow-hidden bg-slate-50/20 transition-all">
          <textarea
            id="draft-editor-textarea"
            v-model="userEditedDraft"
            rows="18"
            class="w-full font-mono text-sm sm:text-base p-5 border-0 focus:outline-none focus:ring-0 leading-relaxed bg-transparent text-slate-900 resize-y"
            :placeholder="t.editor.editorPlaceholder"
          ></textarea>

          <!-- Floating Word Count & Shortcut Pill -->
          <div class="border-t border-slate-200/80 bg-slate-50/80 px-4 py-2.5 flex items-center justify-between text-xs text-slate-500 flex-wrap gap-2">
            <span class="flex items-center gap-1.5">
              <span>{{ t.editor.editorFooterHint }}</span>
            </span>
            <div class="flex items-center gap-3 font-mono text-xs">
              <span class="font-semibold text-slate-700">{{ userEditedDraft.length }} {{ t.editor.chars }}</span>
              <span class="text-slate-300">|</span>
              <span class="font-semibold text-indigo-700">{{ currentWordCount }} {{ t.editor.words }}</span>
              <span class="text-slate-300">|</span>
              <span class="text-slate-600">{{ t.holographic.readMinutes.replace('{minutes}', String(readingMinutes)) }}</span>
              <span class="text-slate-300">|</span>
              <button
                type="button"
                @click="copyCurrentDraft"
                class="text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer underline"
              >
                {{ copied ? t.editor.copiedBtn : t.editor.copyAll }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Diff View -->
      <div v-else-if="activeView === 'diff'" class="space-y-4">
        <!-- Diff Mode Selector -->
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-slate-600 uppercase tracking-wider">{{ t.editor.comparisonLabel }}</span>
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 font-mono font-medium">{{ t.editor.legendAiDraft }}</span>
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-mono font-medium">{{ t.editor.legendYourEdits }}</span>
          </div>

          <div class="inline-flex rounded-xl border border-slate-200 p-1 bg-slate-100 text-xs shadow-2xs">
            <button
              type="button"
              @click="diffLayout = 'inline'"
              class="px-3 py-1 rounded-lg transition-all cursor-pointer"
              :class="diffLayout === 'inline' ? 'bg-white font-bold text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'"
            >
              {{ t.editor.unified }}
            </button>
            <button
              type="button"
              @click="diffLayout = 'split'"
              class="px-3 py-1 rounded-lg transition-all cursor-pointer"
              :class="diffLayout === 'split' ? 'bg-white font-bold text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'"
            >
              {{ t.editor.sideBySide }}
            </button>
          </div>
        </div>

        <!-- If no changes -->
        <div v-if="!hasDiff" class="py-12 text-center text-slate-400 space-y-2 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200">
          <div class="text-3xl">⚖️</div>
          <p class="font-bold text-sm text-slate-700">{{ t.editor.noDiffTitle }}</p>
          <p class="text-xs text-slate-500">{{ t.editor.noDiffBody }}</p>
        </div>

        <!-- Inline Diff View -->
        <div
          v-else-if="diffLayout === 'inline'"
          class="rounded-2xl border border-slate-800 bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto max-h-[500px] overflow-y-auto shadow-inner"
        >
          <div
            v-for="(line, idx) in diffLines"
            :key="idx"
            class="px-4 py-1 flex items-start space-x-3 leading-relaxed transition-colors font-mono"
            :class="{
              'bg-emerald-950/70 text-emerald-300 border-l-4 border-emerald-500': line.type === 'added',
              'bg-rose-950/70 text-rose-300 border-l-4 border-rose-500 line-through opacity-80': line.type === 'removed',
              'text-slate-300 hover:bg-slate-900/60': line.type === 'unchanged'
            }"
          >
            <span class="w-6 text-right select-none opacity-40 flex-shrink-0 font-mono">
              {{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}
            </span>
            <span class="whitespace-pre-wrap flex-1">{{ line.text || ' ' }}</span>
          </div>
        </div>

        <!-- Side by Side Split Diff View -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Left: AI Original -->
          <div class="rounded-2xl border border-rose-200/90 bg-rose-50/30 p-4 space-y-2 shadow-2xs">
            <div class="text-xs font-bold text-rose-900 uppercase tracking-wider flex items-center justify-between pb-2 border-b border-rose-200/60">
              <span>{{ t.editor.originalTab }}</span>
              <span class="font-mono text-[10px] bg-rose-100 px-2 py-0.5 rounded text-rose-800">Baseline</span>
            </div>
            <pre class="font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed max-h-[450px] overflow-y-auto">{{ originalDraft }}</pre>
          </div>

          <!-- Right: User Final -->
          <div class="rounded-2xl border border-emerald-200/90 bg-emerald-50/30 p-4 space-y-2 shadow-2xs">
            <div class="text-xs font-bold text-emerald-900 uppercase tracking-wider flex items-center justify-between pb-2 border-b border-emerald-200/60">
              <span>{{ t.editor.editTab }}</span>
              <span class="font-mono text-[10px] bg-emerald-100 px-2 py-0.5 rounded text-emerald-800">+{{ addedLinesCount }} lines</span>
            </div>
            <pre class="font-mono text-xs text-slate-900 whitespace-pre-wrap leading-relaxed max-h-[450px] overflow-y-auto font-medium">{{ userEditedDraft }}</pre>
          </div>
        </div>
      </div>

      <!-- 3. Formatted Live Preview -->
      <div v-else-if="activeView === 'preview'" class="prose max-w-none text-slate-800 leading-relaxed font-serif text-base py-3 px-2">
        <div v-html="renderedHtml"></div>
      </div>
    </div>

    <!-- Footer Toolbar -->
    <div class="bg-slate-50/90 border-t border-slate-200/80 p-4 px-6 flex items-center justify-between flex-wrap gap-3">
      <button
        type="button"
        @click="$emit('backToOutlines')"
        class="text-sm font-semibold text-slate-600 hover:text-slate-900 cursor-pointer flex items-center gap-1 active:scale-95 transition"
      >
        {{ t.editor.reselectOutline }}
      </button>

      <div class="flex items-center space-x-4">
        <span class="text-xs text-slate-500 font-medium hidden sm:inline">
          {{ t.editor.readyToExtract }}
        </span>

        <button
          type="button"
          @click="triggerExtraction"
          :disabled="loading || !userEditedDraft.trim()"
          class="px-5 py-2.5 text-sm font-bold rounded-xl text-white shadow-md transition-all flex items-center space-x-2 cursor-pointer active:scale-95"
          :class="loading || !userEditedDraft.trim()
            ? 'bg-purple-400 cursor-not-allowed'
            : 'bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:from-purple-700 hover:to-indigo-700'"
        >
          <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span v-else>🧬</span>
          <span>{{ loading ? t.editor.extracting : t.editor.extractBtn }}</span>
        </button>
      </div>
    </div>

    <!-- Distribute Modal -->
    <MultiPlatformDistributeModal
      :show="showDistributeModal"
      :content="userEditedDraft"
      :title="title || topic"
      @close="showDistributeModal = false"
      @update:show="(val: boolean) => (showDistributeModal = val)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from '../i18n'
import ViewpointReview from './ViewpointReview.vue'
import MultiPlatformDistributeModal from './MultiPlatformDistributeModal.vue'
import {
  fetchCognitiveProfile,
  fetchPersonas,
  fetchProducts,
  fetchStories,
  type ViewpointJudgment,
  type CoreViewpoint,
  type CognitiveTrait,
  type CognitiveDimension,
  type IPPersona,
  type ProductVaultItem,
  type EpisodicStoryItem,
} from '../services/api'
import { saveDraftToArchive } from '../services/historyStorage'

const { t, locale } = useI18n()

interface Props {
  originalDraft: string
  initialEditedDraft?: string
  draftId?: string
  blueprintTitle?: string
  blueprintId?: string
  sourceMaterial?: any
  lineageSnapshot?: Record<string, any>
  title: string
  summary?: string
  topic?: string
  coreViewpoints?: CoreViewpoint[]
  activePersona?: IPPersona | null
  activeProduct?: ProductVaultItem | null
  boundStories?: EpisodicStoryItem[]
  personaId?: string
  productId?: string
  storyIds?: string[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  initialEditedDraft: undefined,
  draftId: '',
  blueprintTitle: '',
  blueprintId: '',
  sourceMaterial: null,
  lineageSnapshot: () => ({}),
  summary: '',
  topic: '',
  coreViewpoints: () => [],
  activePersona: null,
  activeProduct: null,
  boundStories: () => [],
  personaId: '',
  productId: '',
  storyIds: () => [],
  loading: false,
})

const emit = defineEmits<{
  (e: 'update:draftId', value: string): void
  (e: 'update:editedDraft', value: string): void
  (e: 'extractDNA', payload: { originalDraft: string; userEditedDraft: string; viewpointJudgments?: ViewpointJudgment[] }): void
  (e: 'extract-dna', payload: { originalDraft: string; userEditedDraft: string; viewpointJudgments?: ViewpointJudgment[] }): void
  (e: 'backToOutlines'): void
}>()

const normalizeText = (t: string) => (t || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')

// UI state
const activeView = ref<'edit' | 'diff' | 'preview'>('edit')
const diffLayout = ref<'inline' | 'split'>('inline')
const userEditedDraft = ref(
  props.initialEditedDraft !== undefined
    ? normalizeText(props.initialEditedDraft)
    : normalizeText(props.originalDraft)
)
const copied = ref(false)
const showDistributeModal = ref(false)
const currentJudgments = ref<ViewpointJudgment[]>([])

// Module 1: History Archive Saving
const isSavingArchive = ref(false)
const savedArchiveSuccess = ref(false)
const currentDraftId = ref<string>(props.draftId || '')

watch(
  () => props.draftId,
  (newId) => {
    if (newId) currentDraftId.value = newId
  }
)

async function handleSaveToHistory() {
  isSavingArchive.value = true
  try {
    const saved = await saveDraftToArchive({
      id: currentDraftId.value || undefined,
      topic: props.topic || props.title || (locale.value === 'zh' ? '草稿作品' : 'Draft'),
      content: userEditedDraft.value,
      original_draft: props.originalDraft,
      summary: props.summary,
      blueprint_title: props.blueprintTitle || undefined,
      blueprint_id: props.blueprintId || undefined,
      source_material_id: props.sourceMaterial?.id || props.lineageSnapshot?.source_material_id,
      lineage_snapshot: buildLineageSnapshot(),
      word_count: currentWordCount.value,
    })
    if (saved?.id) {
      currentDraftId.value = saved.id
      emit('update:draftId', saved.id)
    }
    savedArchiveSuccess.value = true
    setTimeout(() => {
      savedArchiveSuccess.value = false
    }, 2500)
  } catch (e) {
    console.error('Failed to save draft to archive:', e)
  } finally {
    isSavingArchive.value = false
  }
}

// Module 2: Holographic IP Memory Board state & Persona/Product/Story bindings
const activeTraits = ref<CognitiveTrait[]>([])
const showDnaBoard = ref(true)

const internalPersona = ref<IPPersona | null>(null)
const internalProduct = ref<ProductVaultItem | null>(null)
const internalStories = ref<EpisodicStoryItem[]>([])

const currentPersona = computed(() => props.activePersona || internalPersona.value)
const currentProduct = computed(() => props.activeProduct || internalProduct.value)
const currentStories = computed(() => {
  if (props.boundStories && props.boundStories.length > 0) return props.boundStories
  return internalStories.value
})

function buildLineageSnapshot() {
  return {
    ...(props.lineageSnapshot || {}),
    ...(props.sourceMaterial ? {
      source_material_id: props.sourceMaterial.id,
      source_title: props.sourceMaterial.title,
      source_platform: props.sourceMaterial.source_platform,
      source_author: props.sourceMaterial.source_author,
      source_url: props.sourceMaterial.source_url
    } : {}),
    persona_id: currentPersona.value?.id || props.personaId || props.lineageSnapshot?.persona_id,
    persona_name: currentPersona.value?.name,
    product_id: currentProduct.value?.id || props.productId || props.lineageSnapshot?.product_id,
    product_name: currentProduct.value?.product_name,
    story_ids: currentStories.value.map(s => s.id),
  }
}

const loadActiveTraits = async () => {
  try {
    const profile = await fetchCognitiveProfile()
    activeTraits.value = (profile.traits || []).filter(
      (t) => t.status === 'active' || t.status === 'pinned'
    )
  } catch {
    // offline graceful
  }
}

const loadFallbackMemoryAssets = async () => {
  try {
    const [allPersonas, allProducts, allStories] = await Promise.all([
      fetchPersonas().catch(() => []),
      fetchProducts().catch(() => []),
      fetchStories().catch(() => []),
    ])
    const effPersonaId = props.personaId || props.lineageSnapshot?.persona_id
    const effProductId = props.productId || props.lineageSnapshot?.product_id
    const effStoryIds = (props.storyIds && props.storyIds.length > 0)
      ? props.storyIds
      : (props.lineageSnapshot?.story_ids || [])

    if (!props.activePersona && effPersonaId && allPersonas.length > 0) {
      internalPersona.value = allPersonas.find(p => p.id === effPersonaId) || null
    }
    if (!props.activeProduct && effProductId && allProducts.length > 0) {
      internalProduct.value = allProducts.find(p => p.id === effProductId) || null
    }
    if ((!props.boundStories || props.boundStories.length === 0) && allStories.length > 0 && effStoryIds.length > 0) {
      internalStories.value = allStories.filter(s => effStoryIds.includes(s.id))
    }
  } catch (e) {
    console.error('Failed to load fallback memory assets in DraftEditor:', e)
  }
}

onMounted(async () => {
  await Promise.all([loadActiveTraits(), loadFallbackMemoryAssets()])
  // Auto-archive draft initially
  if (userEditedDraft.value.trim() && !currentDraftId.value) {
    saveDraftToArchive({
      id: currentDraftId.value || undefined,
      topic: props.topic || props.title || (locale.value === 'zh' ? '草稿作品' : 'Draft'),
      content: userEditedDraft.value,
      original_draft: props.originalDraft,
      summary: props.summary,
      blueprint_title: props.blueprintTitle || undefined,
      blueprint_id: props.blueprintId || undefined,
      source_material_id: props.sourceMaterial?.id || props.lineageSnapshot?.source_material_id,
      lineage_snapshot: buildLineageSnapshot(),
      word_count: currentWordCount.value,
    }).then((saved) => {
      if (saved?.id) {
        currentDraftId.value = saved.id
        emit('update:draftId', saved.id)
      }
    })
  }
})

// Dynamic hit detection
function isTraitHit(trait: CognitiveTrait): boolean {
  const text = (userEditedDraft.value + ' ' + (props.originalDraft || '')).toLowerCase()
  const statement = (trait.statement || '').toLowerCase()
  if (!statement) return false

  // 1. Direct inclusion
  if (text.includes(statement)) return true

  // 2. Token / keyword matches (e.g. phrases inside quotes or key keywords > 1 char)
  const tokens = statement
    .replace(/[，。、“”‘’：；！!？?\/()\[\]\-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length >= 2)

  let matches = 0
  for (const token of tokens) {
    if (text.includes(token)) {
      matches++
    }
  }
  return matches >= 1
}

const hitCount = computed(() => {
  return activeTraits.value.filter((t) => isTraitHit(t)).length
})

function traitConfidenceLabel(score: number): string {
  const pct = Math.round(score <= 1.0 ? score * 100 : Math.min(100, score * 10))
  return `${pct}%`
}

function dimensionLabel(dim: CognitiveDimension): string {
  switch (dim) {
    case 'vocabulary':
      return '📚 词汇习惯'
    case 'logic_preference':
      return '🧩 论证逻辑'
    case 'core_value':
      return '🎯 核心价值观'
    case 'viewpoint_stance':
      return '⚔️ 审议立场'
    default:
      return '🧬 认知特征'
  }
}

function dimensionBadgeClass(dim: CognitiveDimension): string {
  switch (dim) {
    case 'vocabulary':
      return 'bg-blue-100 text-blue-800 border border-blue-200'
    case 'logic_preference':
      return 'bg-amber-100 text-amber-800 border border-amber-200'
    case 'core_value':
      return 'bg-purple-100 text-purple-800 border border-purple-200'
    case 'viewpoint_stance':
      return 'bg-indigo-100 text-indigo-800 border border-indigo-200'
    default:
      return 'bg-slate-100 text-slate-700 border border-slate-200'
  }
}

const handleJudgmentsUpdate = (judgments: ViewpointJudgment[]) => {
  currentJudgments.value = judgments
}

// Sync when props change
watch(
  () => props.originalDraft,
  (newVal) => {
    if (props.initialEditedDraft === undefined) {
      userEditedDraft.value = normalizeText(newVal)
    }
  }
)

watch(
  () => props.initialEditedDraft,
  (newVal) => {
    if (newVal !== undefined) {
      userEditedDraft.value = normalizeText(newVal)
    }
  }
)

watch(userEditedDraft, (newVal) => {
  emit('update:editedDraft', newVal)
})

// Accurate word / character counting
const currentWordCount = computed(() => {
  const text = userEditedDraft.value.trim()
  if (!text) return 0
  const cjkChars = (text.match(/[\u4e00-\u9fff]/g) || []).length
  const words = (text.match(/[a-zA-Z0-9]+(?:['\u2019\-][a-zA-Z0-9]+)*/g) || []).length
  return cjkChars + words
})

const readingMinutes = computed(() => {
  return Math.max(1, Math.ceil(currentWordCount.value / 300))
})

// Markdown formatting helper
function insertMarkdown(prefix: string, suffix: string = '') {
  const el = document.getElementById('draft-editor-textarea') as HTMLTextAreaElement | null
  if (!el) {
    userEditedDraft.value += `${prefix}${suffix}`
    return
  }
  const start = el.selectionStart || 0
  const end = el.selectionEnd || 0
  const selected = userEditedDraft.value.substring(start, end)
  const replacement = `${prefix}${selected || '内容'}${suffix}`
  userEditedDraft.value = userEditedDraft.value.substring(0, start) + replacement + userEditedDraft.value.substring(end)
  setTimeout(() => {
    el.focus()
    el.setSelectionRange(start + prefix.length, start + prefix.length + (selected ? selected.length : 2))
  }, 50)
}

// Diff detection
const hasTextDiff = computed(() => {
  return normalizeText(props.originalDraft).trim() !== normalizeText(userEditedDraft.value).trim()
})

const hasActiveJudgments = computed(() => {
  return currentJudgments.value.some(
    (j) => j.selected_key !== 'agree' || (j.custom_note && j.custom_note.trim())
  )
})

const hasDiff = computed(() => {
  return hasTextDiff.value || hasActiveJudgments.value
})

// Line-based diff computation using LCS algorithm
interface DiffLine {
  type: 'added' | 'removed' | 'unchanged'
  text: string
  origLineNum?: number
  newLineNum?: number
}

const diffLines = computed<DiffLine[]>(() => {
  const orig = normalizeText(props.originalDraft).split('\n')
  const mod = normalizeText(userEditedDraft.value).split('\n')
  const m = orig.length
  const n = mod.length

  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < n; j++) {
      if (orig[i] === mod[j]) {
        dp[i + 1][j + 1] = dp[i][j] + 1
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1])
      }
    }
  }

  const result: DiffLine[] = []
  let i = m
  let j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && orig[i - 1] === mod[j - 1]) {
      result.push({ type: 'unchanged', text: orig[i - 1], origLineNum: i, newLineNum: j })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'added', text: mod[j - 1], newLineNum: j })
      j--
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      result.push({ type: 'removed', text: orig[i - 1], origLineNum: i })
      i--
    }
  }
  return result.reverse()
})

const addedLinesCount = computed(() => {
  return diffLines.value.filter((l) => l.type === 'added').length
})

const removedLinesCount = computed(() => {
  return diffLines.value.filter((l) => l.type === 'removed').length
})

const resetToOriginal = () => {
  userEditedDraft.value = normalizeText(props.originalDraft)
}

const triggerExtraction = () => {
  if (!userEditedDraft.value.trim()) {
    return
  }
  // Auto-save edited version to archive
  saveDraftToArchive({
    id: currentDraftId.value || undefined,
    topic: props.topic || props.title || (locale.value === 'zh' ? '精修草稿' : 'Refined Draft'),
    content: userEditedDraft.value,
    original_draft: props.originalDraft,
    summary: props.summary,
    blueprint_title: props.blueprintTitle || undefined,
    blueprint_id: props.blueprintId || undefined,
    source_material_id: props.sourceMaterial?.id || props.lineageSnapshot?.source_material_id,
    lineage_snapshot: buildLineageSnapshot(),
    word_count: currentWordCount.value,
  }).then((saved) => {
    if (saved?.id) {
      currentDraftId.value = saved.id
      emit('update:draftId', saved.id)
    }
  })

  const payload = {
    originalDraft: normalizeText(props.originalDraft),
    userEditedDraft: normalizeText(userEditedDraft.value),
    viewpointJudgments: currentJudgments.value,
  }
  emit('extractDNA', payload)
  emit('extract-dna', payload)
}

// Clipboard copy
const copyCurrentDraft = async () => {
  try {
    await navigator.clipboard.writeText(userEditedDraft.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = userEditedDraft.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  }
}

// Markdown parser
const renderedHtml = computed(() => {
  const raw = userEditedDraft.value
  if (!raw) return ''

  let html = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Headings
  html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-slate-900 mt-6 mb-2">$1</h3>')
  html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-slate-900 mt-8 mb-3 border-b border-slate-100 pb-1">$1</h2>')
  html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-black text-slate-900 mt-8 mb-4">$1</h1>')

  // Blockquotes
  html = html.replace(/^> (.*$)/gim, '<blockquote class="border-l-4 border-indigo-300 pl-4 py-1 italic my-3 text-slate-600 bg-slate-50/50 rounded-r">$1</blockquote>')

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong class="font-bold text-slate-900">$1</strong>')
  html = html.replace(/\*(.*?)\*/gim, '<em class="italic text-slate-700">$1</em>')

  // Bullet items
  html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="ml-5 list-disc my-1 text-slate-700">$1</li>')

  // Paragraphs
  const paragraphs = html.split(/\n\n+/)
  return paragraphs
    .map((p) => {
      const trimmed = p.trim()
      if (!trimmed) return ''
      if (trimmed.startsWith('<h') || trimmed.startsWith('<li') || trimmed.startsWith('<blockquote')) {
        return trimmed
      }
      return `<p class="my-3 leading-relaxed text-slate-700">${trimmed.replace(/\n/g, '<br/>')}</p>`
    })
    .join('\n')
})
</script>
