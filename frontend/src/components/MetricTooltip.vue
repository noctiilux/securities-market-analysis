<script setup>
defineProps({
  text: { type: String, required: true },
});
</script>

<template>
  <span class="metric-tip" :title="text" tabindex="0">?</span>
</template>

<style scoped>
.metric-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border-radius: 50%;
  background: #d6c6b5;
  color: #3d2a2a;
  font-size: 11px;
  font-weight: 700;
  cursor: help;
  vertical-align: middle;
}
</style>
