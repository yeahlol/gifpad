  $(document).ready(function(){
    $("input:text, select").change(function(){
      var arr = $("#ready-uploaded-gif form .publisher_gif :input").serializeArray();
      var Associarr = {};  /* 空のリテラルobjで生成した連想配列 */
      $.each(arr, function(index, item){
        Associarr[item.name] = item.value;
      });
      delete Associarr["hidden"];
      var jsonstr = JSON.stringify(Associarr) /* json文字列に変換 */

      console.log(jsonstr);
      $("#hidden").val(jsonstr);
    });
  });
