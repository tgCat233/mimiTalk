<script setup>
import { computed, ref } from 'vue'
import NewChatRow from './NewChatRow.vue'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  avatars: { type: Object, default: () => ({ heroes: {}, groups: {} }) },
  characters: { type: Array, default: () => [] },
})

const emit = defineEmits(['select', 'create', 'remove', 'favorite'])

const menuOpen = ref(false)
const menuKind = ref('')
const query = ref('')

const favoriteCharacters = computed(() =>
  props.characters.filter((character) => character.favorite),
)
const singleCharacters = computed(() =>
  props.characters.filter((character) => character.kind !== 'group'),
)
const groupCharacters = computed(() =>
  props.characters.filter((character) => character.kind === 'group'),
)
const searchResults = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return []
  return props.characters.filter((character) =>
    character.name.toLowerCase().includes(keyword),
  )
})
const menuCharacters = computed(() => {
  if (menuKind.value === 'favorite') return favoriteCharacters.value
  if (menuKind.value === 'single') return singleCharacters.value
  if (menuKind.value === 'group') return groupCharacters.value
  return []
})
const menuTitle = computed(() => {
  if (menuKind.value === 'favorite') return '收藏'
  if (menuKind.value === 'single') return '单聊'
  return '群聊'
})

function toggleMenu() {
  if (menuOpen.value) {
    closeMenu()
    return
  }
  menuOpen.value = true
  menuKind.value = ''
  query.value = ''
}

function closeMenu() {
  menuOpen.value = false
  menuKind.value = ''
  query.value = ''
}

function openKind(kind) {
  menuKind.value = kind
  query.value = ''
}

function pick(character) {
  if (character.conversation_id) return
  closeMenu()
  emit('create', character.id)
}

function toggleFavorite(character) {
  emit('favorite', character.id, !character.favorite)
}

function nameOf(conversation) {
  return conversation.title || '未命名会话'
}

function previewOf(conversation) {
  return conversation.last_message || ''
}

function conversationAvatar(conversation) {
  const hero = props.avatars.heroes?.[conversation.title]
  if (hero?.url) return hero.url
  const group = props.avatars.groups?.[conversation.title]
  return group?.url || group?.members?.[0] || ''
}

function initialOf(conversation) {
  return nameOf(conversation).slice(0, 1)
}
</script>

<template>
  <div class="side-list" role="listbox" aria-label="会话列表">
    <div class="new-chat-wrap">
      <button
        class="side-entry side-entry-action"
        type="button"
        @click.stop="toggleMenu"
      >
        <span class="side-entry-avatar avatar-frame">
          <span class="avatar" aria-hidden="true">+</span>
        </span>
        <span class="side-entry-text">
          <strong>新建会话</strong>
          <small>从角色与群聊中选择</small>
        </span>
      </button>

      <div v-if="menuOpen" class="new-chat-backdrop" @click="closeMenu"></div>
      <div v-if="menuOpen" class="new-chat-menu">
        <template v-if="!menuKind">
          <input
            v-model="query"
            class="new-chat-search"
            type="search"
            placeholder="搜索角色或群聊"
            aria-label="搜索角色或群聊"
            @click.stop
          />

          <template v-if="query.trim()">
            <div class="new-chat-scroll">
              <NewChatRow
                v-for="character in searchResults"
                :key="character.id"
                :character="character"
                @pick="pick"
                @favorite="toggleFavorite"
              />
              <p v-if="!searchResults.length" class="new-chat-empty">
                没有匹配的角色或群聊
              </p>
            </div>
          </template>

          <template v-else>
            <button
              v-if="favoriteCharacters.length"
              class="new-chat-category"
              type="button"
              @click.stop="openKind('favorite')"
            >
              <span class="new-chat-category-label">
                <span class="new-chat-category-star">★</span> 收藏
              </span>
              <small>{{ favoriteCharacters.length }} 个</small>
              <span class="new-chat-chevron">›</span>
            </button>
            <button
              class="new-chat-category"
              type="button"
              @click.stop="openKind('single')"
            >
              <span>单聊</span>
              <small>{{ singleCharacters.length }} 个</small>
              <span class="new-chat-chevron">›</span>
            </button>
            <button
              class="new-chat-category"
              type="button"
              @click.stop="openKind('group')"
            >
              <span>群聊</span>
              <small>{{ groupCharacters.length }} 个</small>
              <span class="new-chat-chevron">›</span>
            </button>
          </template>
        </template>

        <template v-else>
          <div class="new-chat-menu-head">
            <button
              class="new-chat-back"
              type="button"
              aria-label="返回"
              @click.stop="menuKind = ''"
            >
              ‹
            </button>
            <strong>{{ menuTitle }}</strong>
            <small>{{ menuCharacters.length }} 个</small>
          </div>
          <div class="new-chat-scroll">
            <NewChatRow
              v-for="character in menuCharacters"
              :key="character.id"
              :character="character"
              @pick="pick"
              @favorite="toggleFavorite"
            />
            <p v-if="!menuCharacters.length" class="new-chat-empty">
              {{ menuKind === 'favorite' ? '还没有收藏的角色或群聊' : '暂无联系人' }}
            </p>
          </div>
        </template>
      </div>
    </div>

    <div
      v-for="conversation in conversations"
      :key="conversation.id"
      class="side-entry"
      :class="{ active: conversation.id === activeId }"
      role="option"
      tabindex="0"
      :aria-selected="conversation.id === activeId"
      @click="$emit('select', conversation.id)"
      @keydown.enter="$emit('select', conversation.id)"
    >
      <span class="side-entry-avatar avatar-frame">
        <span
          v-if="conversationAvatar(conversation)"
          class="avatar has-image"
          :style="{ backgroundImage: `url(${conversationAvatar(conversation)})` }"
        ></span>
        <span v-else class="avatar">{{ initialOf(conversation) }}</span>
      </span>
      <span class="side-entry-text">
        <strong>{{ nameOf(conversation) }}</strong>
        <small>{{ previewOf(conversation) }}</small>
      </span>
      <button
        class="side-entry-remove"
        type="button"
        title="删除会话"
        aria-label="删除会话"
        @click.stop="$emit('remove', conversation.id)"
      >
        ×
      </button>
    </div>

    <p v-if="!conversations.length" class="empty-state side-empty">
      还没有会话，点上方新建。
    </p>
  </div>
</template>
