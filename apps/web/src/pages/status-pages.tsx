import { HttpStatusPage } from "./http-status-page";

type StatusPageProps = {
  onBack: () => void;
};

export function NotFoundPage({ onBack }: StatusPageProps) {
  return (
    <HttpStatusPage
      code={404}
      title="页面不存在"
      description="你访问的地址不存在，可能已被移动或输入有误。"
      onBack={onBack}
    />
  );
}

export function NotImplementedPage({ onBack }: StatusPageProps) {
  return (
    <HttpStatusPage
      code={501}
      title="功能尚未实现"
      description="该功能还在开发中，请稍后再试或返回首页继续使用。"
      onBack={onBack}
    />
  );
}
