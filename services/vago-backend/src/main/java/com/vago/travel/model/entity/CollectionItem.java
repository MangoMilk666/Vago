package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CollectionItem {
    private String uuid;
    private String collectionUuid;
    private String guideUuid;
    private String userUuid;
    private String note; //收藏时备注
    private LocalDateTime createdAt;
}
