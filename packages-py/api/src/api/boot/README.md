# boot/

启动编排：FastAPI lifespan 与渐进式预热。

- `lifespan.py` — `create_lifespan()`：应用启动时 `init_db`，关闭时收尾
- `warmup.py` — 先响应壳层探活（`current_phase()`），再后台 `ensure_warmed()`：
  加载 DB、挂闲鱼 token 探活调度与商品监控轮询调度（`domains.watch.scheduler`）
