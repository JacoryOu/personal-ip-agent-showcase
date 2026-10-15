<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 glass-card-dark overflow-y-auto"
    @click.self="handleClose"
  >
    <div
      class="bg-white rounded-3xl max-w-3xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200/80 space-y-5 my-8 max-h-[90vh] flex flex-col relative overflow-hidden toast-enter"
    >
      <!-- Ambient Glow Decorator -->
      <div
        class="absolute -top-16 -right-16 w-56 h-56 bg-gradient-to-br from-emerald-200/40 via-teal-200/20 to-transparent rounded-full blur-3xl pointer-events-none"
      ></div>

      <!-- Celebration Toast Overlay / Banner -->
      <transition
        enter-active-class="transform transition ease-out duration-300"
        enter-from-class="translate-y-[-100%] opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition ease-in duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="celebrationMessage"
          class="absolute top-4 left-6 right-6 z-30 p-4 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 text-white shadow-xl flex items-center gap-3 border border-emerald-300/40 animate-pulse"
        >
          <span class="text-2xl shrink-0">🎉</span>
          <div class="flex-1 text-xs sm:text-sm font-bold">
            {{ celebrationMessage }}
          </div>
        </div>
      </transition>

      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-slate-100 pb-4 shrink-0 relative z-10">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white flex items-center justify-center text-xl shadow-sm"
          >
            📦
          </div>
          <div>
            <h3 class="text-lg font-black text-slate-900 flex items-center gap-2">
              <span>{{ t.product_vault?.extractModalTitle || '智能产品心智反向萃取' }}</span>
              <span
                class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200"
              >
                1-Click Reverse Extraction
              </span>
            </h3>
            <p class="text-xs text-slate-500 mt-0.5 max-w-xl">
              {{ t.product_vault?.extractModalSubtitle || '粘贴产品文案或说明书，AI 自动提炼适用体质、劝退禁忌、第一人称自用体感与转化钩子。' }}
            </p>
          </div>
        </div>
        <button
          type="button"
          @click="handleClose"
          :disabled="isExtracting || isSaving"
          class="w-8 h-8 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center font-bold text-lg transition cursor-pointer disabled:opacity-40"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <!-- State 1: Input Raw Text Form -->
      <div v-if="!extractedData" class="space-y-4 overflow-y-auto pr-1 flex-1 relative z-10">
        <!-- Quick Sample Presets -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              {{ t.product_vault?.quickSamplesLabel || '快速载入真实好物样例测试：' }}
            </label>
            <button
              v-if="rawText.trim()"
              type="button"
              @click="rawText = ''"
              class="text-[11px] text-slate-400 hover:text-rose-500 transition cursor-pointer"
            >
              {{ t.product_vault?.clearText || '清空内容' }}
            </button>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              type="button"
              v-for="(sample, idx) in samplePresets"
              :key="idx"
              @click="loadSample(sample.content)"
              class="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 hover:bg-emerald-50 hover:text-emerald-800 text-slate-700 border border-slate-200/80 transition cursor-pointer active:scale-95 flex items-center gap-1.5"
            >
              <span>{{ sample.icon }}</span>
              <span>{{ sample.label }}</span>
            </button>
          </div>
        </div>

        <!-- Raw Textarea -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
            <span>{{ t.product_vault?.rawTextLabel || '产品详情文案 / 供应商笔记 / 说明书 (Raw Product Text)' }}</span>
            <span class="text-slate-400 font-mono text-[11px] font-normal">
              {{ rawText.length }} 字
            </span>
          </label>
          <textarea
            v-model="rawText"
            :placeholder="t.product_vault?.rawTextPlaceholder || '在此粘贴你的产品详情文案、配料表、功效说明或供应商推介语...'"
            rows="10"
            class="w-full bg-slate-50/80 border border-slate-200 rounded-2xl p-4 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none transition resize-none leading-relaxed"
          ></textarea>
        </div>

        <!-- Error Message Banner -->
        <div
          v-if="errorMessage"
          class="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2"
        >
          <span>⚠️</span>
          <span>{{ errorMessage }}</span>
        </div>
      </div>

      <!-- State 2: Extracted Preview & Fine-tuning -->
      <div v-else class="space-y-4 overflow-y-auto pr-1 flex-1 relative z-10">
        <!-- Preview Banner -->
        <div class="p-3.5 rounded-2xl bg-emerald-50/80 border border-emerald-100 flex items-center justify-between text-xs">
          <div class="flex items-center gap-2 text-emerald-950 font-bold">
            <span class="text-base">🪄</span>
            <span>{{ t.product_vault?.previewBanner || '已成功逆向提炼产品核心心智！你可以在此微调，确认后一键存入好物库。' }}</span>
          </div>
          <button
            type="button"
            @click="extractedData = null"
            class="text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 underline cursor-pointer shrink-0 ml-2"
          >
            {{ t.product_vault?.reInputText || '← 重新输入文案' }}
          </button>
        </div>

        <!-- Extracted Product Card -->
        <div class="bg-gradient-to-br from-emerald-50/30 via-teal-50/20 to-white border border-emerald-100 rounded-3xl p-5 shadow-xs space-y-4">
          <!-- Card Header / Title & Category -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-emerald-100/60 pb-3">
            <div class="flex-1">
              <label class="block text-[11px] font-bold text-slate-600 mb-1">
                {{ t.product_vault?.productNameLabel || '产品品名' }}
              </label>
              <input
                v-model="extractedProduct.product_name"
                :placeholder="t.product_vault?.productNamePlaceholder || '输入产品品名'"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-sm font-black text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none"
              />
            </div>
            <div class="w-full sm:w-48">
              <label class="block text-[11px] font-bold text-slate-600 mb-1">
                {{ t.product_vault?.categoryLabel || '品类/形态' }}
              </label>
              <input
                v-model="extractedProduct.category"
                :placeholder="t.product_vault?.categoryPlaceholder || '品类标签'"
                class="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-emerald-800 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none"
              />
            </div>
          </div>

          <!-- Core Ingredients Chips & Text -->
          <div>
            <label class="block text-[11px] font-bold text-slate-700 mb-1 flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span>🌿</span>
                <span>{{ t.product_vault?.coreIngredients || '核心成分 / 亮点工艺' }}</span>
              </span>
            </label>
            <div v-if="ingredientChips.length" class="flex flex-wrap gap-1.5 mb-2">
              <span
                v-for="(chip, idx) in ingredientChips"
                :key="idx"
                class="px-2 py-0.5 rounded-lg text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200/80"
              >
                {{ chip }}
              </span>
            </div>
            <textarea
              v-model="extractedProduct.core_ingredients"
              rows="2"
              :placeholder="t.product_vault?.ingredientsPlaceholder || '核心配方与工艺亮点...'"
              class="w-full bg-white border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 leading-relaxed focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none"
            ></textarea>
          </div>

          <!-- Dual Column: Suitable Conditions vs Taboos / 劝退人群 -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <!-- Left: Suitable Conditions -->
            <div class="bg-emerald-50/50 border border-emerald-200/70 rounded-2xl p-3.5 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-black text-emerald-900 flex items-center gap-1.5">
                  <span>✅</span>
                  <span>{{ t.product_vault?.suitableConditions || '精准适用体质与人群' }}</span>
                </span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                  Target
                </span>
              </div>
              <textarea
                v-model="extractedProduct.suitable_conditions"
                rows="3"
                :placeholder="t.product_vault?.suitablePlaceholder || '适用人群与日常场景...'"
                class="w-full bg-white border border-emerald-200 rounded-xl p-2 text-xs text-slate-800 leading-relaxed focus:ring-2 focus:ring-emerald-200 outline-none"
              ></textarea>
            </div>

            <!-- Right: Taboos / 劝退禁忌 (Prominent Warning Styling) -->
            <div class="bg-rose-50/60 border-2 border-rose-200 rounded-2xl p-3.5 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs font-black text-rose-900 flex items-center gap-1.5">
                  <span>⚠️</span>
                  <span>{{ t.product_vault?.taboos || '劝退禁忌人群 (信任基石)' }}</span>
                </span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
                  Taboos
                </span>
              </div>
              <textarea
                v-model="extractedProduct.taboos"
                rows="3"
                :placeholder="t.product_vault?.taboosPlaceholder || '禁忌人群、不适用体质与风险提醒...'"
                class="w-full bg-white border border-rose-200 rounded-xl p-2 text-xs text-slate-800 leading-relaxed focus:ring-2 focus:ring-rose-200 outline-none"
              ></textarea>
            </div>
          </div>

          <!-- Personal Usage Experience (First-person quote card) -->
          <div class="bg-amber-50/40 border border-amber-200/80 rounded-2xl p-3.5 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-black text-amber-950 flex items-center gap-1.5">
                <span>💬</span>
                <span>{{ t.product_vault?.personalExperience || '第一人称真实自用体验与体感' }}</span>
              </span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                1st Person Voice
              </span>
            </div>
            <textarea
              v-model="extractedProduct.personal_usage_experience"
              rows="3"
              :placeholder="t.product_vault?.experiencePlaceholder || '真实记录你的日常自用场景、体感变化与信任细节...'"
              class="w-full bg-white border border-amber-200 rounded-xl p-2.5 text-xs text-slate-800 leading-relaxed focus:ring-2 focus:ring-amber-200 outline-none"
            ></textarea>
          </div>

          <!-- Conversion Hooks -->
          <div class="bg-indigo-50/40 border border-indigo-200/70 rounded-2xl p-3.5 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-black text-indigo-950 flex items-center gap-1.5">
                <span>🎁</span>
                <span>{{ t.product_vault?.conversionHooks || '低阻力转化引子 (转化钩子)' }}</span>
              </span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">
                Conversion Hook
              </span>
            </div>
            <input
              v-model="extractedProduct.conversion_hooks"
              :placeholder="t.product_vault?.hooksPlaceholder || '私信回复关键词送调理配方、加好友领品鉴装等低阻力钩子...'"
              class="w-full bg-white border border-indigo-200 rounded-xl px-3 py-2 text-xs text-slate-800 leading-relaxed focus:ring-2 focus:ring-indigo-200 outline-none"
            />
          </div>

          <!-- Optional Visual Cover Image -->
          <div class="bg-slate-50/80 border border-slate-200/80 rounded-2xl p-3.5 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-black text-slate-800 flex items-center gap-1.5">
                <span>🖼️</span>
                <span>{{ t.product_vault?.coverImageLabel || '产品封面视觉图 (可选)' }}</span>
              </span>
              <span class="text-[10px] text-slate-400">{{ t.product_vault?.coverImageHint || '用于好物卡片与朋友圈' }}</span>
            </div>
            <div v-if="extractedProduct.cover_image" class="relative w-full h-28 rounded-xl overflow-hidden border border-slate-200 group">
              <img :src="resolveImageUrl(extractedProduct.cover_image)" class="w-full h-full object-cover" />
              <button
                type="button"
                @click="extractedProduct.cover_image = ''"
                class="absolute top-1.5 right-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-full p-1 text-xs shadow-md transition cursor-pointer"
                :title="t.product_vault?.removeImageBtn || '移除'"
              >
                ✕
              </button>
            </div>
            <div v-else class="flex items-center gap-2">
              <label class="border border-dashed border-slate-300 hover:border-emerald-500 rounded-xl px-3 py-2 text-center cursor-pointer transition bg-white shrink-0">
                <input type="file" accept="image/*" class="hidden" @change="handleUploadCover" :disabled="isUploadingCover" />
                <span class="text-xs text-slate-600 font-semibold flex items-center gap-1">
                  <span>{{ isUploadingCover ? '⏳' : '📸' }}</span>
                  <span>{{ isUploadingCover ? (t.product_vault?.uploadingImage || '上传中...') : (t.product_vault?.uploadImageBtn || '上传本地图') }}</span>
                </span>
              </label>
              <input
                v-model="extractedProduct.cover_image"
                type="url"
                :placeholder="t.product_vault?.orInputUrlPlaceholder || '或直接输入封面图片 URL'"
                class="flex-1 bg-white border border-slate-200 rounded-xl px-2.5 py-2 text-xs text-slate-700 outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>
        </div>

        <!-- Error Message Banner in State 2 -->
        <div
          v-if="errorMessage"
          class="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2"
        >
          <span>⚠️</span>
          <span>{{ errorMessage }}</span>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="border-t border-slate-100 pt-4 flex items-center justify-end gap-3 shrink-0 relative z-10">
        <button
          type="button"
          @click="handleClose"
          :disabled="isExtracting || isSaving"
          class="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition cursor-pointer disabled:opacity-50"
        >
          {{ t.product_vault?.cancelBtn || '取消' }}
        </button>

        <!-- CTA 1: Start Extract -->
        <button
          v-if="!extractedData"
          type="button"
          @click="handleStartExtract"
          :disabled="!rawText.trim() || isExtracting"
          class="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-md shadow-emerald-500/20 transition active:scale-95 cursor-pointer disabled:opacity-50 flex items-center gap-2"
        >
          <span v-if="isExtracting" class="animate-spin">⏳</span>
          <span v-else>✨</span>
          <span>{{ isExtracting ? (t.product_vault?.extractingBtn || '正在反向萃取产品心智...') : (t.product_vault?.startExtractBtn || '开始智能萃取') }}</span>
        </button>

        <!-- CTA 2: Save Only & Save and Set Active -->
        <template v-else>
          <button
            type="button"
            @click="handleSaveOnly"
            :disabled="isSaving || !extractedProduct.product_name?.trim()"
            class="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition active:scale-95 cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
          >
            <span>📥</span>
            <span>{{ isSaving && !isSavingAsActive ? (t.product_vault?.savingBtn || '正在入库...') : (t.product_vault?.saveOnlyBtn || '仅入库') }}</span>
          </button>

          <button
            type="button"
            @click="handleSaveAndSetActive"
            :disabled="isSaving || !extractedProduct.product_name?.trim()"
            class="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 hover:from-emerald-700 hover:to-indigo-700 shadow-md shadow-emerald-500/25 transition active:scale-95 cursor-pointer disabled:opacity-50 flex items-center gap-2"
          >
            <span v-if="isSaving && isSavingAsActive" class="animate-spin">⏳</span>
            <span v-else>🌟</span>
            <span>{{ isSaving && isSavingAsActive ? (t.product_vault?.savingBtn || '正在入库...') : (t.product_vault?.saveAndSetActiveBtn || '🌟 一键入库并设为主推') }}</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useI18n } from '../i18n'
import {
  extractProductFromText,
  createProduct,
  updateProduct,
  uploadProductImage,
  resolveImageUrl,
  type ProductVaultItem,
} from '../services/api'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', product: ProductVaultItem): void
}>()

const { t } = useI18n()

const rawText = ref('')
const isExtracting = ref(false)
const isSaving = ref(false)
const isSavingAsActive = ref(false)
const isUploadingCover = ref(false)
const errorMessage = ref('')
const celebrationMessage = ref('')
const extractedData = ref<any | null>(null)

async function handleUploadCover(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  isUploadingCover.value = true
  try {
    const res = await uploadProductImage(file)
    extractedProduct.cover_image = res.url
  } catch (err: any) {
    alert(`上传封面图失败: ${err.message || err}`)
  } finally {
    isUploadingCover.value = false
    target.value = ''
  }
}

const extractedProduct = reactive<Partial<ProductVaultItem>>({
  product_name: '',
  category: '',
  core_ingredients: '',
  suitable_conditions: '',
  taboos: '',
  personal_usage_experience: '',
  conversion_hooks: '',
  is_active: true,
})

const ingredientChips = computed(() => {
  const text = extractedProduct.core_ingredients || ''
  if (!text.trim()) return []
  return text
    .split(/[,，、\n]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && s.length <= 20)
    .slice(0, 8)
})

const samplePresets = computed(() => [
  {
    icon: '🍵',
    label: t.value.product_vault?.samplePreset1 || '新会陈皮老白茶 (调湿健脾)',
    content: `品名：梅江老树15年陈皮配高山寿眉老白茶
品类：药食同源茶饮 / 办公元气饮
核心配料与工艺：新会梅江核心产区老树二红皮（干仓陈化15年）、福鼎太姥山原生态老白茶（陈香寿眉）。纯手工炭焙拼配，无任何人工香精与防腐剂。
适合体质与场景：长期伏案久坐办公族、空调房咽喉干燥不适、常年体内湿气重腹胀、熬夜疲劳容易犯困的人群。
禁忌与劝退人群：急性胃溃疡发作期人群、孕期女性以及对茶多酚极度敏感易失眠者夜间不建议饮用。
真实自用感受：我自己做茶八年，熬夜赶方案时每天雷打不动泡一壶。梅江陈皮标志性的药香和白茶的甘甜融合得恰到好处，顺滑下喉整个人胸腔温润舒展，下午两点喝完完全不犯困，身体毫无负担。
转化引流钩子：私信回复【喝茶】送你一份自用的《节气祛湿喝茶调理表》以及 5g 便携试饮装。`,
  },
  {
    icon: '🥧',
    label: t.value.product_vault?.samplePreset2 || '茯苓八珍糕 (养胃体弱)',
    content: `产品名称：手工现蒸山药茯苓八珍糕
品类：传统古法健脾养胃食养糕点
配料亮点：选用岳西茯苓、焦作温县垆土铁棍山药、九华山黄精、莲子、白扁豆、薏苡仁、芡实，辅以微量纯麦芽糖。古法慢火蒸制，软糯不粘牙。
适合人群：脾胃虚弱食少腹胀、大便溏薄不成形、晨起面部浮肿、常感疲乏四肢无力者。
禁忌与劝退：湿热体质舌苔厚黄腻者、严格控糖的重度糖尿病患者、2岁以下婴幼儿请勿食用。
真实自用感受：生完宝宝后我的脾胃垮得厉害，稍微吃点油腻就胃胀腹泻。我妈妈特意找老中医学了这个方子手工做给我吃。每天早餐温开水送服两块，坚持了三周，不仅大便成形了，早上起来舌头两侧齿痕也消退了很多。
转化引流引子：点击下方或私聊我，送你一份《八珍糕脾胃体质对照自测清单》和新鲜现做体验试吃盒。`,
  },
  {
    icon: '🌰',
    label: t.value.product_vault?.samplePreset3 || '古法九蒸九晒黑芝麻丸 (润燥固发)',
    content: `产品品名：传统柴火九蒸九晒黑芝麻黄精丸
品类：深山九蒸九晒滋补食丸
成分与工艺：江西鄱阳湖油麻、九华山九蒸九晒黄精、深山原酿冬蜜。历经九次柴火蒸透与日光自然暴晒，油脂充分分解，黑芝麻不再燥热油腻。
适用体质：经常熬夜脱发掉发、发缝变宽、白发早生、容易头昏耳鸣、精血不足的年轻打工人。
劝退禁忌：严重腹泻便溏急性期、内热重痤疮痘痘爆发期人群暂不建议食用。
真实自用感受：奔三之后发缝越来越宽，每天梳头掉一把。市面上很多机器压的芝麻丸又油又甜，腻得咽不下去。这款九蒸九晒的手工丸子打开就是浓郁天然的纯谷物烘烤香，嚼起来微甜不粘牙，坚持吃了半年，发质明显变得粗壮有光泽，枕头上掉发少了一大半。
转化钩子：私信发送【养发】，免费领取我整理的《防脱养发食疗日常作息指南》。`,
  },
])

function loadSample(text: string) {
  rawText.value = text
  errorMessage.value = ''
}

function handleClose() {
  if (isExtracting.value || isSaving.value) return
  emit('close')
}

// Reset state when modal is opened
watch(
  () => props.show,
  (val) => {
    if (val) {
      errorMessage.value = ''
      celebrationMessage.value = ''
      if (!rawText.value) {
        // preserve or start fresh
      }
    }
  }
)

function heuristicExtract(text: string): Partial<ProductVaultItem> {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  let name = ''
  let category = '好物交付方案'
  let ingredients = ''
  let suitable = ''
  let taboos = ''
  let experience = ''
  let hooks = ''

  for (const line of lines) {
    if (/^(品名|产品名称|产品品名|名称|Name)[:：]/i.test(line)) {
      name = line.replace(/^(品名|产品名称|产品品名|名称|Name)[:：]/i, '').trim()
    } else if (/^(品类|形态|类型|Category)[:：]/i.test(line)) {
      category = line.replace(/^(品类|形态|类型|Category)[:：]/i, '').trim()
    } else if (/^(核心配料|配料|成分|亮点|工艺)[:：]/i.test(line)) {
      ingredients = line.replace(/^(核心配料|配料|成分|亮点|工艺)[:：]/i, '').trim()
    } else if (/^(适合体质|适用人群|适合人群|适用体质|人群)[:：]/i.test(line)) {
      suitable = line.replace(/^(适合体质|适用人群|适合人群|适用体质|人群)[:：]/i, '').trim()
    } else if (/^(禁忌与劝退|禁忌|劝退|不适合|注意事项)[:：]/i.test(line)) {
      taboos = line.replace(/^(禁忌与劝退|禁忌|劝退|不适合|注意事项)[:：]/i, '').trim()
    } else if (/^(真实自用感受|自用体验|自用感受|真实自用|自用体验与体感)[:：]/i.test(line)) {
      experience = line.replace(/^(真实自用感受|自用体验|自用感受|真实自用|自用体验与体感)[:：]/i, '').trim()
    } else if (/^(转化引流钩子|转化引子|引流钩子|引子|钩子)[:：]/i.test(line)) {
      hooks = line.replace(/^(转化引流钩子|转化引子|引流钩子|引子|钩子)[:：]/i, '').trim()
    }
  }

  if (!name && lines.length > 0) {
    name = lines[0].slice(0, 30)
  }

  return {
    product_name: name || '私域精选好物',
    category: category || '滋补调养',
    core_ingredients: ingredients || text.slice(0, 100),
    suitable_conditions: suitable || '追求高品质生活、注重身心健康调理的私域读者与学员',
    taboos: taboos || '特殊过敏体质、急性期患者请遵医嘱慎用',
    personal_usage_experience: experience || '我自己长期在日常中使用并深度体验，口感与体感反馈极佳，值得长期自留与交付。',
    conversion_hooks: hooks || '私信回复【好物】，领取专属体验礼遇与使用手册',
    is_active: true,
  }
}

async function handleStartExtract() {
  const text = rawText.value.trim()
  if (!text || isExtracting.value) return

  isExtracting.value = true
  errorMessage.value = ''

  try {
    let p: any = null
    try {
      const res = await extractProductFromText(text, false)
      extractedData.value = res
      p = res.product || (res as any)
    } catch (apiErr: any) {
      console.warn('Backend extractProductFromText not reachable or failed, using intelligent client parsing fallback:', apiErr)
      p = heuristicExtract(text)
      extractedData.value = { product: p }
    }

    extractedProduct.product_name = p.product_name || p.name || '私域好物'
    extractedProduct.category = p.category || '私域交付方案'
    extractedProduct.core_ingredients = p.core_ingredients || ''
    extractedProduct.suitable_conditions = p.suitable_conditions || ''
    extractedProduct.taboos = p.taboos || ''
    extractedProduct.personal_usage_experience = p.personal_usage_experience || ''
    extractedProduct.conversion_hooks = p.conversion_hooks || ''
    extractedProduct.is_active = true
    extractedProduct.cover_image = p.cover_image || ''
    extractedProduct.gallery_images = p.gallery_images ? [...p.gallery_images] : []
    extractedProduct.service_rights_images = p.service_rights_images ? [...p.service_rights_images] : []
  } catch (err: any) {
    console.error('Extract product failed:', err)
    errorMessage.value = err.message || '萃取失败，请检查文本或重试'
  } finally {
    isExtracting.value = false
  }
}

async function executeSave(setActive: boolean) {
  if (isSaving.value || !extractedProduct.product_name?.trim()) return

  isSaving.value = true
  isSavingAsActive.value = setActive
  errorMessage.value = ''

  try {
    let savedProduct: ProductVaultItem

    const payload: Partial<ProductVaultItem> = {
      product_name: extractedProduct.product_name?.trim() || '',
      category: extractedProduct.category?.trim() || '好物交付方案',
      core_ingredients: extractedProduct.core_ingredients?.trim() || '',
      suitable_conditions: extractedProduct.suitable_conditions?.trim() || '',
      taboos: extractedProduct.taboos?.trim() || '',
      personal_usage_experience: extractedProduct.personal_usage_experience?.trim() || '',
      conversion_hooks: extractedProduct.conversion_hooks?.trim() || '',
      is_active: setActive,
      cover_image: extractedProduct.cover_image || '',
      gallery_images: extractedProduct.gallery_images ? [...extractedProduct.gallery_images] : [],
      service_rights_images: extractedProduct.service_rights_images ? [...extractedProduct.service_rights_images] : [],
    }

    if (extractedData.value?.product?.id && extractedData.value?.saved) {
      savedProduct = await updateProduct(extractedData.value.product.id, payload)
    } else {
      savedProduct = await createProduct(payload)
    }

    const template = t.value.product_vault?.saveSuccessCelebration || '🎉 太棒了！好物档案「{name}」已成功入库！'
    celebrationMessage.value = template.replace('{name}', savedProduct.product_name)

    emit('saved', savedProduct)

    setTimeout(() => {
      celebrationMessage.value = ''
      extractedData.value = null
      rawText.value = ''
      emit('close')
    }, 1200)
  } catch (err: any) {
    console.error('Failed to save product:', err)
    errorMessage.value = err.message || '保存入库失败，请重试'
  } finally {
    isSaving.value = false
  }
}

function handleSaveOnly() {
  executeSave(false)
}

function handleSaveAndSetActive() {
  executeSave(true)
}
</script>
