export interface SubtitleToken {
  text: string;
  pinyin?: string | null;
  meaning?: string | null;
  start_index?: number | null;
  end_index?: number | null;
}

export interface SubtitleLine {
  id?: number | null;
  start: number;
  end: number;
  text: string;
  translation?: string | null;
  tokens?: SubtitleToken[];
  processing_status?: "raw" | "processing" | "processed" | "failed";
}

export interface SubtitleResponse {
  video_id: string;
  title?: string | null;
  subtitles: SubtitleLine[];
}

export interface SubtitleBatch {
  video_id: string;
  batch_index: number;
  start_time: number;
  end_time: number;
  subtitles: SubtitleLine[];
}

export interface ProcessingProgress {
  video_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  phase?: string;
  phase_progress?: number;
  processed_batches: number;
  total_batches: number;
  processed_subtitles: number;
  total_subtitles: number;
  progress: number;
}

export interface ImportedVideo {
  id: number;
  youtube_video_id: string;
  title: string;
  url: string;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  channel_name?: string | null;
  channel_id?: string | null;
  upload_date?: string | null;
  metadata_fetched_at?: string | null;
  language: string;
  processing_status: string;
  tags: string[];
  created_at: string;
}

export interface VideoProgress {
  youtube_video_id: string;
  current_time: number;
  completed: boolean;
  last_watched_at: string;
}

export interface DictionaryMeaning {
  meaning: string;
  definition?: string | null;
}

export interface DictionaryContext {
  original_sentence?: string | null;
  selected_meaning?: string | null;
  phrase?: string | null;
  phrase_pinyin?: string | null;
  phrase_meaning?: string | null;
  explanation?: string | null;
}

export interface DictionaryCollocation {
  text: string;
  pinyin: string;
  meaning: string;
}

export interface DictionaryExample {
  chinese: string;
  pinyin: string;
  vietnamese: string;
}

export interface DictionaryEntry {
  word: string;
  pinyin?: string | null;
  meaning: string;
  part_of_speech?: string | null;
  contextual_meaning?: string | null;
  example_zh?: string | null;
  example_vi?: string | null;
  meanings?: DictionaryMeaning[];
  context?: DictionaryContext | null;
  collocations?: DictionaryCollocation[];
  examples?: DictionaryExample[];
  enrichment_error?: string | null;
}

export interface SavedVocabulary {
  id: number;
  word: string;
  pinyin?: string | null;
  meaning?: string | null;
  youtube_video_id: string;
  video_title: string;
  subtitle_sentence: string;
  timestamp: number;
  created_at: string;
}
