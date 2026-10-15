# cause_flow

节点按因果顺序出现，SVG 连线用 stroke-dashoffset 从时间计算；一次只强调当前节点。
所有运动遵守 clip.renderAt(t)，不得依赖墙上时钟。
