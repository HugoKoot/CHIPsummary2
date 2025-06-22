<template>
  <div class="chat-window column fit">
    <!-- Messages Area -->
    <div
      class="messages-area col q-pa-md"
      ref="messagesDiv"
    >
      <q-chat-message
        v-for="item in messageStore.messages"
        :key="item.message + item.timestamp"
        :text="[item.message]"
        :sent="item.user?.human"
        :name="item.user?.name"
        class="q-mb-sm"
      />
      <q-chat-message
        :name="botUser?.name"
        :sent="botUser?.human"
        v-if="waiting"
        class="q-mb-sm"
      >
        <q-spinner-dots size="2rem" />
      </q-chat-message>
    </div>

    <!-- Input Area -->
    <div class="input-area q-pa-md">
      <q-input
        filled
        v-model="text"
        placeholder="Type your message..."
        @keyup.enter="submit"
        class="chat-input q-mb-md"
      >
        <template v-slot:before>
          <q-avatar color="primary" text-color="white" icon="account_circle" />
        </template>
        <template v-slot:after>
          <q-btn 
            round 
            dense 
            flat 
            icon="send" 
            color="primary"
            @click="submit"
            :disable="!text.trim()"
          />
        </template>
      </q-input>
      
      <!-- END CHAT Button -->
      <div class="row justify-center">
        <q-btn
          color="negative"
          label="END CHAT"
          @click="endChat"
          class="q-px-lg"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang='ts'>
import { ref, nextTick, onMounted, onUnmounted } from 'vue';
import { useMessageStore } from 'src/stores/message-store';
import { useUserStore } from 'src/stores/user-store';
import { useQuasar } from 'quasar';

const $q = useQuasar();
const emit = defineEmits(['reloadVisualization']);

const messageStore = useMessageStore();
const userStore = useUserStore();

// Set user for now, later on I suppose it can come from login/etc
userStore.user = { name: 'John', human: true };
const botUser = { name: 'Bot', human: false };

const text = ref('');
var waiting = false;

async function endChat() {
  console.log('\'END CHAT\' button clicked, endChat function started.');

  if (messageStore.messages.length === 0) {
    console.log('No messages to save, showing warning notification.');
    $q.notify({
      color: 'warning',
      message: 'No messages to save',
      position: 'top'
    });
    return;
  }

  console.log('Attempting to save chat. Messages count:', messageStore.messages.length);
  try {
    const response = await fetch('/api/save-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: messageStore.messages,
        patient_name: userStore.user?.name
      })
    });

    console.log('Save chat API response received:', response);

    if (response.ok) {
      console.log('Chat save process started successfully.');
      $q.notify({
        color: 'info',
        message: 'Chat saving process started...',
        position: 'top',
        icon: 'hourglass_top'
      });
      // We don't clear messages here anymore, we wait for the 'done' sse event
    } else {
      console.error('Failed to start save chat process.', response);
      throw new Error('Failed to save chat');
    }
  } catch (error) {
    console.error('Error during save chat operation:', error);
    $q.notify({
      color: 'negative',
      message: 'Failed to save chat',
      position: 'top'
    });
  }
}

async function submit() {
  if (text.value) {
    var timestamp = new Date().toISOString();
    messageStore.addMessage({ message: text.value, user: userStore.user, timestamp: timestamp });

    // Send message to backend
    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_name: userStore.user?.name,
        sentence: text.value,
        timestamp: timestamp
      }),
    };

    text.value = '';
    fetch('/api/submit', requestOptions).then((response) => {
      console.log(response);
    }
    );
    waiting = true;

    scrollToBottom();
    emit('reloadVisualization');
  }
}

async function scrollToBottom() {
  await nextTick();
  if (messagesDiv.value) {
    messagesDiv.value.scrollTop = messagesDiv.value.scrollHeight;
  }
}

const messagesDiv = ref<HTMLDivElement | null>(null);

var source: EventSource;
onMounted(() => {
  source = new EventSource('/api/stream');
  source.addEventListener(
    'response',
    function (event) {
      var data = JSON.parse(event.data);
      messageStore.addMessage({
        message: data.message,
        user: botUser,
        timestamp: new Date().toISOString()
      });
      waiting = false;
      scrollToBottom();
      console.log(`Received response: ${data.message}`);
    },
    false,
  );
  source.addEventListener(
    'progress',
    function (event) {
      const data = JSON.parse(event.data);
      console.log(`Received progress: ${data.message}`);

      const notificationConfig = {
        message: data.message,
        position: 'top' as const,
        timeout: 4000, // ms
        group: 'chat-saving'
      };

      if (data.status === 'done') {
        $q.notify({
          ...notificationConfig,
          color: 'positive',
          icon: 'done',
          timeout: 5000
        });
        messageStore.clearMessages();
      } else if (data.status === 'error') {
        $q.notify({
          ...notificationConfig,
          color: 'negative',
          icon: 'error',
          timeout: 8000
        });
      }
      else {
        // Dismiss the previous notification in the same group
        $q.notify({
          ...notificationConfig,
          color: 'info',
          spinner: true,
        });
      }
    },
    false
  );
});

onUnmounted(() => {
  source?.close();
});
</script>

<style scoped>
.chat-window {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: #ffffff;
  min-height: 0; /* Important for proper flex scrolling */
}

.input-area {
  border-top: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.chat-input {
  background: white;
}

/* Custom scrollbar for messages area */
.messages-area::-webkit-scrollbar {
  width: 6px;
}

.messages-area::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.messages-area::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.messages-area::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
