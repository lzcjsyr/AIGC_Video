<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1 class="app-title">智能视频制作系统</h1>
        <nav class="nav-menu">
          <el-menu mode="horizontal" :router="true" :default-active="$route.path">
            <el-menu-item index="/upload">文件上传</el-menu-item>
            <el-menu-item index="/projects">项目管理</el-menu-item>
            <el-menu-item index="/config">系统配置</el-menu-item>
          </el-menu>
        </nav>
      </div>
    </el-header>
    
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
// Vue 3 Composition API
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.app-title {
  margin: 0;
  color: #333;
  font-size: 24px;
}

.nav-menu {
  height: 100%;
}

.app-main {
  background: #f5f5f5;
  padding: 20px;
}
</style>