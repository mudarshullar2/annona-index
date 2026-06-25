-- creating a watermark table
create table watermark_table
(
    last_load varchar(200)
);

-- add a surrogate key (since we don't have a date id column)
alter table supplier_lead_time_datasource add load_id bigint identity(1,1);

-- checking if load_id was added
select * from supplier_lead_time_datasource;

insert into watermark_table
values (1);

select * from watermark_table;

select max(load_id) as max_id from supplier_lead_time_datasource;