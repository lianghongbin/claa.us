/* 覆盖 SimpleUI menu.js：传递 eid；子菜单 index 不与叶子冲突；更新高亮时不重建整棵菜单 */
Vue.component("sub-menu", {
  props: ["menus", "fold"],
  methods: {
    openTab(data, eid) {
      if (window.app && typeof window.app.openTab === "function") {
        window.app.openTab(data, eid);
      }
    },
  },
  template: `
        <div>
            <template v-for="item in menus" :key="item.eid">
                <el-menu-item
                    v-if="!item.models"
                    :index="String(item.eid)"
                    @click.native.stop="openTab(item, item.eid)"
                >
                    <i :class="'menu-icon ' + item.icon"></i>
                    <span v-show="!fold">{{ item.name }}</span>
                </el-menu-item>
                <el-submenu v-else :index="'sub-' + item.eid">
                    <template slot="title">
                        <i :class="'menu-icon ' + item.icon"></i>
                        <span v-show="!fold">{{ item.name }}</span>
                    </template>
                    <sub-menu :menus="item.models" :fold="fold"></sub-menu>
                </el-submenu>
            </template>
        </div>
    `,
});

Vue.component("multiple-menu", {
  props: ["menus", "menuActive", "fold"],
  watch: {
    menuActive: function (val) {
      this.applyActive(val);
    },
  },
  mounted: function () {
    this.applyActive(this.menuActive);
  },
  methods: {
    applyActive: function (val) {
      var menu = this.$refs.sideMenu;
      if (!menu || val == null || val === "") {
        return;
      }
      menu.activeIndex = String(val);
    },
  },
  template: `
        <el-menu
            ref="sideMenu"
            :unique-opened="true"
            :default-active="String(menuActive)"
            :collapse="fold"
            :collapse-transition="false"
        >
            <sub-menu :menus="menus" :fold="fold"></sub-menu>
        </el-menu>
    `,
});
