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
 *   - **数组先整体、再逐元素。** 整个值满足判定就直接用它；不满足、且它是数组时，
 *     才把数组当候选列表按顺序找。所以 `isString([a, b], "")` 是「在 a、b 里找字符串」，
 *     而 `isArray([1, 2], [])` 是「它本身是数组」。反过来「在一个数组里找数组」不支持 ——
 *     那种需求不存在，而先逐元素会让「取一个数组字段」这个最常见写法静默拿到兜底值。
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
 *
 * 数组的处理顺序是**先整体、再逐元素**：整个值满足判定就直接用它；不满足、
 * 且它是个数组时，才把数组当候选列表按顺序找。这个顺序不能颠倒 ——
 * 若先逐元素，`isArray([1, 2], [])` 会去 `[1, 2]` **里面**找数组，返回兜底 `[]`，
 * 于是「取一个数组字段」这种最常见用法会静默拿到空数组。
 */
export function picker<T>(guard: TypeGuard<T>) {
  return <F>(values: unknown, fallback: F): T | F => {
    if (guard(values)) return values;
    if (Array.isArray(values)) {
      for (const candidate of values) {
        if (guard(candidate)) return candidate;
      }
    }
    return fallback;
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
