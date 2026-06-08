// Centralized Japanese UI strings. All user-facing copy lives here so the
// audience (Japanese-language policy researchers, journalists, analysts)
// reads a consistent vocabulary. Code/comments stay in English.

import type { EventType } from "./types";

export const ja = {
  appTitle: "千島列島 軍事動向モニター",
  appSubtitle: "公開衛星データによる軍事関連活動の継続監視（オープンソース・インテリジェンス）",
  tagline:
    "本ツールは無料の公開データから抽出した「候補シグナル」を表示します。自動検知は確定した軍事活動ではありません。",

  // Disclaimer / positioning
  unverifiedBadge: "未確認",
  unverifiedNotice:
    "すべての検知は自動抽出による未確認の候補です。元データへのリンクから人間が確認してください。",
  freeDataNotice: "継続監視レイヤーは無料データソースのみで稼働しています。",

  // Data origin banners
  sampleDataBanner:
    "サンプルデータを表示中です。パイプライン（FIRMS）を実行すると実データに置き換わります。",
  emptyDataBanner:
    "現在のウィンドウに該当イベントはありません。パイプラインを実行するとイベントが表示されます。",

  // Sections
  facilitiesHeading: "監視対象施設",
  eventFeedHeading: "イベントフィード",
  timelineHeading: "タイムライン",
  detailHeading: "施設の詳細",

  // Map / controls
  dateRangeLabel: "表示期間",
  allFacilities: "すべての施設",
  resetSelection: "選択を解除",
  legendHeading: "凡例",
  signalStrength: "シグナル強度",

  // Event detail
  eventDate: "観測日",
  eventType: "種別",
  eventSource: "データソース",
  eventNotes: "備考",
  retrievedAt: "取得日時",
  viewSource: "元データを確認",
  noEventsForFacility: "この施設には該当期間のイベントがありません。",
  selectFacilityPrompt: "地図上のマーカーまたは一覧から施設を選択してください。",
  eventsCount: (n: number) => `${n} 件のイベント`,

  // Facility types
  facilityType: (t: string): string =>
    ({
      airbase: "航空基地",
      coastal_defense: "沿岸防衛施設",
      garrison: "守備隊",
      other: "その他",
    })[t] ?? t,

  // Event types
  eventTypeLabel: (t: EventType): string =>
    ({
      construction: "建設",
      thermal: "熱異常",
      clearance: "地表改変",
      naval: "艦船活動",
      other: "その他",
    })[t] ?? t,

  // Footer
  dataSources: "データソース",
  dataSourcesList:
    "NASA FIRMS（VIIRS / MODIS 熱異常）、Sentinel-1 SAR（予定）、Sentinel-2 光学（予定）",
  about: "本ツールについて",
} as const;

export type Strings = typeof ja;
