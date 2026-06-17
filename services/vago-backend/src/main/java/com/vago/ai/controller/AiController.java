package com.vago.ai.controller;

import com.vago.ai.model.dto.AiPlanSaveDTO;
import com.vago.ai.model.vo.AiPlanSaveVO;
import com.vago.ai.service.AiService;
import com.vago.common.Result;
import com.vago.context.BaseContext;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * AI 业务控制器。
 *
 * <p>重构后职责收窄：仅处理 AI 行程保存类业务逻辑（纯 Java + MySQL）。
 *
 * <p>AI 对话推理端点（/chat、/chat/stream）已直连 Python vago-ai：
 * 由 Nginx（生产）或 Vite Proxy（开发）将 /api/v1/ai/chat* 请求直接转发至 Python，
 * JWT 鉴权由 Python 侧 get_current_user_uuid 依赖自行验证。
 */
@Tag(name = "AI 行程规划")
@RestController
@RequestMapping("/api/v1/ai")
@Slf4j
public class AiController {

    @Autowired
    private AiService aiService;

    @Operation(
        summary = "保存 AI 行程为草稿",
        description = "将 AI 生成的结构化行程计划保存为计划草稿（Plan），\n\n"
            + "日期可选，保存后用户可在计划页面继续编辑。"
    )
    @PostMapping("/plans/save-draft")
    public Result<AiPlanSaveVO> saveDraft(@Valid @RequestBody AiPlanSaveDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("[AiController] 保存AI行程为草稿 user={}", userUuid);
        return Result.success(aiService.saveAsDraft(dto, userUuid));
    }

    @Operation(
        summary = "保存 AI 行程为正式行程",
        description = "将 AI 生成的结构化行程计划保存为正式行程（Trip），\n\n"
            + "要求出发日期和返回日期必填。"
    )
    @PostMapping("/plans/save-trip")
    public Result<AiPlanSaveVO> saveTrip(@Valid @RequestBody AiPlanSaveDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("[AiController] 保存AI行程为正式行程 user={}", userUuid);
        return Result.success(aiService.saveAsTrip(dto, userUuid));
    }
}
