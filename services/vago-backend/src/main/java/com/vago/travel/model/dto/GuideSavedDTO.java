package com.vago.travel.model.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class GuideSavedDTO {
    private String collectionUuid;
    private String guideUuid;
    private String note; //收藏时备注

}
