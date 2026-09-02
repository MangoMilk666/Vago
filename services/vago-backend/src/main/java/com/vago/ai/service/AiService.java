package com.vago.ai.service;

import com.vago.ai.model.dto.AiPlanSaveDTO;
import com.vago.ai.model.vo.AiPlanSaveVO;

/** Java 兼容窗口内仅保留 AI 结构化行程保存。 */
public interface AiService {
    AiPlanSaveVO saveAsDraft(AiPlanSaveDTO dto, String userUuid);
    AiPlanSaveVO saveAsTrip(AiPlanSaveDTO dto, String userUuid);
}
