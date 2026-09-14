/**
 * 值类型判定与取值。
 *
 * 职责：
 *   把「类型判定 + 兜底」这一族写法收敛成一次调用：`isString(x, fallback)`
 *   等价于 `typeof x === "string" ? x : fallback`，并且可以一次给多个候选值。
 *
 * 设计说明：
 *   - 解决的是**类型判定型三元**（`typeof x === "string" ? x : ""`），
 *     尤其是嵌套那种「先试 A，再试 B，都没有再兜底」。普通的二选一分支
 *     （两种载荷形状、条件渲染）不属于这个范畴，仍该用 `if` / 三元 ——
 *     套判定器只会更绕。
 *   - 返回类型是 `T | F`，兜底值决定结果类型：传 `undefined` 得 `T | undefined`，
 *     传 `""` 得 `string`，不需要在调用点标注。
 *   - **数组一律被当作候选列表。** 所以「判断某个值本身是不是数组」要写成
 *     `isArray([value], fallback)`；`isArray(value, fallback)` 是「在 value 的元素里
 *     找一个数组」。这是本模块唯一的语义歧义点，刻意选了「数组即候选」，
 *     因为多候选比单值判断更常用，且这样才能表达 `isString([a, b], "")`。
 *   - **判定不转换。** `isNumber("12")` 是 `false`。需要转换用各自的转换函数，
 *     两者语义不同（判定是「信任这个值」，转换是「尽量救回来」），不要混。
 *   - 判定器是成套的：`isString / isNumber / isBoolean / isObject / isArray /
 *     isFunction`。缺一个，调用点就会有人再手写一遍 `typeof` 判断 ——
 *     而且常写错（例如把 `NaN` 当 number、把 `null` 当 object）。
 */

/** 类型谓词：判断 `unknown` 是否属于 `T`。 */
export type TypeGuard<T> = (value: unknown) => value is T;

/**
 * 取值器工厂：给一个判定，得到「按顺序取第一个满足判定的候选值，否则兜底」的函数。
 *
 * 这是本模块的类型体操核心 —— 所有判定器都由它派生。加一个类型只需要写一个谓词，
 * 不必再写一遍候选遍历；返回类型 `T | F` 也由这里统一推导。
 */
export function picker<T>(guard: TypeGuard<T>) {
  return <F>(values: unknown, fallback: F): T | F => {
    // 数组即候选列表（见文件头说明）。
    if (Array.isArray(values)) {
      for (const candidate of values) {
        if (guard(candidate)) return candidate;
      }
      return fallback;
    }
    return guard(values) ? values : fallback;
  };
}

/** 字符串判定。 */
export const isString = picker<string>((value): value is string => typeof value === "string");

/**
 * 有限数字判定。
 *
 * `NaN` 与 `±Infinity` 都是 `typeof === "number"`，但让它们流到下游会算出 `NaN`
 * 并一路传染 —— 所以这里一并拒掉。
 */
export const isNumber = picker<number>(
  (value): value is number => typeof value === "number" && Number.isFinite(value),
);

/** 布尔判定。注意 `new Boolean()` 这类包装对象不算 —— 它们 `typeof` 是 "object"。 */
export const isBoolean = picker<boolean>((value): value is boolean => typeof value === "boolean");

/**
 * 普通对象判定。
 *
 * 排除 `null` 与数组：三者的 `typeof` 都是 `"object"`，但只有普通对象能当
 * 「字段容器」用。不做这个排除，`record.items` 拿到数组时会去取 `.length` 之类的
 * 字段名，静默拿到 undefined。
 */
export const isObject = picker<Record<string, unknown>>(
  (value): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value),
);

/** 数组判定。入参语义见文件头：`isArray([x], fb)` 判断的是 `x`。 */
export const isArray = picker<unknown[]>((value): value is unknown[] => Array.isArray(value));

/** 函数判定。 */
export const isFunction = picker<(...args: never[]) => unknown>(
  (value): value is (...args: never[]) => unknown => typeof value === "function",
);
