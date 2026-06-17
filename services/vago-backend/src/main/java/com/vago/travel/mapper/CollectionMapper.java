package com.vago.travel.mapper;

import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.entity.CollectionItem;
import com.vago.travel.model.vo.CollectionVO;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface CollectionMapper {

    @Insert("insert into collections (uuid, user_uuid, name, type, description, created_at, updated_at) " +
            "VALUES (#{uuid}, #{userUuid}, #{name}, #{type}, #{description}, #{created}, #{updated})")
    void insert(Collection c);

    @Select("select uuid, user_uuid, name, type, description, created_at, updated_at from collections where uuid = #{uuid}")
    Collection getByUuid(String uuid);

    @Update("update collections set name = #{name}, description = #{description} where uuid = #{uuid}")
    void update(CollectionUpdateDTO dto);

    /**
     * 删除指定收藏夹下的所有帖子
     */
    @Delete("delete from collection_items where collection_uuid = #{uuid}")
    void deleteByCollection(String uuid);

    @Delete("delete from collections where uuid = #{uuid}")
    void deleteByUuid(String uuid);

    @Select("select uuid, user_uuid, name, type, description, created_at, updated_at from collections where user_uuid = #{userUuid}")
    List<CollectionVO> getListByUserid(String userUuid);

    @Insert("insert into collection_items(uuid, collection_uuid, guide_uuid, user_uuid, note, created_at) " +
            "VALUES (#{uuid}, #{collectionUuid}, #{guideUuid}, #{userUuid}, #{note}, #{createdAt})")
    void saveInto(CollectionItem item);

    @Delete("delete from collection_items where collection_uuid=#{collectionUuid} and guide_uuid = #{guideUuid}")
    void deleteItem(String collectionUuid, String guideUuid);

    /**
     * 获取某收藏夹内的攻略列表id,默认按日期倒序
     */
    @Select("select guide_uuid from collection_items where collection_uuid = #{collectionUuid} order by created_at")
    List<String> getItemsByCollectionId(String collectionUuid);

    @Select("select collection_uuid from collection_items where guide_uuid=#{guideUuid} and user_uuid=#{userUuid}")
    List<String> inWhichCollections(String guideUuid, String userUuid);
}
