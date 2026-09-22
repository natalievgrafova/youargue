export interface Channel {
  id: string
  name: string
  query: string
  filter: string[]
  lang: string
  color: string
}

export interface VideoThread {
  text: string
  author: string
  likes: number
  replies: number
}

export interface Video {
  video_id: string
  title: string
  published_at: string
  channel_id: string
  channel_name: string
  channel_color: string
  thumbnail: string
  url: string
  comment_count: number
  view_count: number
  like_count: number
  threads: VideoThread[]
}

export interface ChannelStats {
  id: string
  name: string
  color: string
  video_count: number
  total_comments: number
  total_views: number
  total_likes: number
  avg_comments: number
}

export interface VideosResponse {
  videos: Video[]
  channel_stats: Record<string, ChannelStats>
  total_videos: number
  total_comments: number
  total_views: number
}

export interface CorpusVideo {
  status?: 'done' | 'queued' | 'running' | 'failed'
  video_id?: string
  title: string
  comment_count: number
  annotator_count?: number
}

export type Confidence = 'high' | 'medium' | 'low'

export interface Comment {
  comment_id: string
  text: string
  author: string
  likes: number
  date: string
  argument_type: string
  confidence: Confidence
}

export interface Topic {
  topic: string
  pro_count: number
  con_count: number
  total: number
  pro_pct: number
  con_pct: number
  pro_comments: Comment[]
  con_comments: Comment[]
}

export interface AnalysisResponse {
  title: string
  lang: string
  total_comments: number
  thread_count: number
  topic_count: number
  topics: Topic[]
}
