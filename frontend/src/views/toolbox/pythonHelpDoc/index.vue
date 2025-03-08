<template>
  <AppPage>
    <div>
      <iframe
          :src="htmlContent"
          width="100%"
          height="800px"
          frameborder="0"
      ></iframe>
    </div>
  </AppPage>
</template>

<script setup>
import {ref} from 'vue';
import AppPage from "@/components/page/AppPage.vue";
import {BACKEND_URL} from "~/build/constant";

const htmlContent = ref(BACKEND_URL + "/static/pythonHelpDoc/index.html");
</script>
