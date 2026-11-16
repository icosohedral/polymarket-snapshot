```md
# 通用极简数据产品配色规范（Light Minimal System）

> 适用于：SaaS / 数据平台 / AI工具 / 管理后台 / 开发者工具  
> 风格：极简、克制、数据优先（类似 Linear / GitHub / Vercel）

---

## 一、设计原则

### 核心思想

- **去主色化**：不依赖品牌色驱动 UI
- **灰度构建结构**：用明度而非颜色区分层级
- **颜色服务数据**：强调色只用于“状态/数据”
- **高留白 + 低干扰**
- **一致性优先于个性**

---

## 二、配色体系结构

```

Base（灰阶） → 构建结构
Text（文字） → 表达层级
Semantic（语义色） → 表达状态
Data（数据色） → 可视化

````

---

## 三、基础色（Base Colors）

### 背景层级

```css
--bg-primary:   #F9FAFB;  /* 页面背景 */
--bg-secondary: #FFFFFF;  /* 卡片 / 容器 */
--bg-tertiary:  #F3F4F6;  /* hover / 分区 */
````

**使用规则：**

* 页面 → primary
* 卡片 → secondary
* hover / 分区 → tertiary

---

### 边界（Border）

```css
--border-subtle: #E5E7EB;
--border-strong: #D1D5DB;
```

**规则：**

* 默认使用 subtle
* 避免重边框
* 优先用 spacing 分层

---

## 四、文字系统（Text Colors）

```css
--text-primary:   #111827;  /* 主信息 */
--text-secondary: #6B7280;  /* 次要信息 */
--text-tertiary:  #9CA3AF;  /* 辅助说明 */
--text-disabled:  #D1D5DB;  /* 禁用 */
```

**原则：**

* 层级靠“灰度”，不是颜色
* 主文本必须高对比
* 不使用彩色文本作为结构元素

---

## 五、语义色（Semantic Colors）

> 用于表达状态，而不是 UI 结构

### 成功（Success）

```css
--success: #22C55E;
--success-soft: #DCFCE7;
```

### 错误（Danger）

```css
--danger: #EF4444;
--danger-soft: #FEE2E2;
```

### 警告（Warning）

```css
--warning: #F59E0B;
--warning-soft: #FEF3C7;
```

---

## 六、数据可视化色（Data Colors）

> 仅用于图表 / heatmap / 分类标签

### 单色渐变（推荐）

```css
--data-1: #DCFCE7;
--data-2: #86EFAC;
--data-3: #22C55E;
--data-4: #15803D;
```

**适用于：**

* Heatmap
* 活跃度
* 强度分布

---

### 多分类（可选）

```css
--data-blue:   #3B82F6;
--data-purple: #8B5CF6;
--data-cyan:   #06B6D4;
--data-orange: #F97316;
--data-pink:   #EC4899;
```

**规则：**

* 不超过 5–6 种
* 不参与 UI 结构

---

## 七、交互状态（Interaction States）

```css
--hover-bg:   #F3F4F6;
--active-bg:  #E5E7EB;
--focus-ring: #9CA3AF;
```

**原则：**

* 轻微变化，不打断视觉一致性
* 避免高饱和 hover 效果

---

## 八、按钮配色策略（无主色方案）

### 默认按钮（Primary 行为但弱视觉）

```css
--btn-bg: #F3F4F6;
--btn-text: #111827;
```

### hover

```css
--btn-hover: #E5E7EB;
```

**特点：**

* 不突出按钮
* 降低“营销感”
* 保持工具属性

---

## 九、使用规范

### ✅ 推荐

* 用灰度构建 UI 结构
* 用语义色表达状态（成功 / 错误）
* 用数据色表达信息强度
* 控制彩色面积（<10%）
* 保持整体低饱和

---

### ❌ 避免

* 多主色竞争
* 用颜色区分布局结构
* 大面积使用高饱和颜色
* 图表颜色污染 UI
* 强 CTA（除非产品需要转化导向）

---

## 十、设计取向对比

| 维度   | 极简数据风 | 传统 SaaS |
| ---- | ----- | ------- |
| 主色   | 无     | 蓝色主导    |
| UI结构 | 灰度    | 彩色区块    |
| 按钮   | 弱视觉   | 强 CTA   |
| 颜色用途 | 数据表达  | 交互引导    |
| 风格   | 克制    | 强引导     |

```
```
