package browser

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// pluginDirName 与 DingDa Rust 侧插件 id 保持一致：浏览器由 Rust 插件系统下载安装，
// 落到 {DINGDA_PLUGINS_DIR}/xhs-mcp-browser/，本模块只负责定位。
const pluginDirName = "xhs-mcp-browser"

// browserBinNames 返回当前平台下内置浏览器的候选可执行文件名。
func browserBinNames() []string {
	switch runtime.GOOS {
	case "darwin":
		return []string{"Chromium", "chrome"}
	case "linux":
		return []string{"chrome", "Chromium"}
	default:
		return []string{"chrome.exe"}
	}
}

// ResolveBrowser 返回内置浏览器可执行文件路径。
// 浏览器下载由 DingDa 应用（Rust 插件系统）接管，本函数只查找不下载；找不到返回 error。
func ResolveBrowser() (string, error) {
	pluginsDir := strings.TrimSpace(os.Getenv("DINGDA_PLUGINS_DIR"))
	if pluginsDir == "" {
		return "", fmt.Errorf(
			"DINGDA_PLUGINS_DIR 未设置，无法定位内置浏览器；请通过 DingDa 应用启动",
		)
	}
	root := filepath.Join(pluginsDir, pluginDirName)
	for _, name := range browserBinNames() {
		if bin := findBinary(root, name); bin != "" {
			return bin, nil
		}
	}
	return "", fmt.Errorf(
		"未在 %s 找到内置浏览器可执行文件；请先在 DingDa 应用内安装「小红书浏览器」插件",
		root,
	)
}

func findBinary(dir, binName string) string {
	var found string
	_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if filepath.Base(path) == binName {
			found = path
			return io.EOF // 提前结束
		}
		return nil
	})
	if found != "" {
		if err := os.Chmod(found, 0o755); err != nil {
			_ = err
		}
	}
	return found
}
