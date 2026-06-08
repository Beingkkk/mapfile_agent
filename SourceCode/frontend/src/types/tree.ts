export interface TreeNode {
  id: string;
  path: string;
  object_type: 'MAP' | 'LAYER' | 'CLASS' | 'STYLE' | 'LABEL' | 'WEB' | 'METADATA' | 'CACHE';
  children: (TreeNode | TreeLeaf)[];
  expanded: boolean;
}

export interface TreeLeaf {
  id: string;
  path: string;
  key: string;
  value: any;
  value_type: 'string' | 'enum' | 'integer' | 'float' | 'boolean' | 'color' | 'array' | 'expression';
  phase: 'datasource' | 'style' | 'service' | 'cache';
  required: boolean;
  derived: boolean;
  default?: any;
  enum?: any[];
  custom: boolean;
  custom_desc?: string;
  user_modified: boolean;
  errors: string[];
}

export interface WSMessage {
  type: string;
  [key: string]: any;
}

export interface ValidationError {
  path: string;
  message: string;
}

export interface QAMessage {
  role: 'user' | 'bot' | 'system' | 'divider' | 'loading';
  text: string;
  time?: string;
  focus_param?: string | null;
}
