import { ProductPanel } from "@/components/product/product-primitives";

export default function AppLoading() {
  return (
    <div
      className="cf-page cf-route-loading"
      aria-busy="true"
      aria-label="Loading workspace"
    >
      <div className="cf-skeleton cf-skeleton--eyebrow" />
      <div className="cf-skeleton cf-skeleton--title" />
      <div className="cf-skeleton cf-skeleton--copy" />
      <ProductPanel className="cf-skeleton-panel">
        <div className="cf-skeleton cf-skeleton--status" />
        <div className="cf-skeleton cf-skeleton--hero" />
        <div className="cf-skeleton cf-skeleton--copy" />
        <div className="cf-skeleton cf-skeleton--button" />
      </ProductPanel>
    </div>
  );
}
