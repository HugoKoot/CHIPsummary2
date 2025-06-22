<template>
  <q-page class="flex flex-center q-pa-md">
    <div class="chat-container">
      <chat-window></chat-window>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import ChatWindow from 'src/components/ChatWindow.vue';
</script>

<style scoped>
.chat-container {
  width: 100%;
  max-width: 800px;
  height: 90vh;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}
</style>
